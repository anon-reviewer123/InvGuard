# flow_1_files/agent.py
# ---- set OpenAI API key (MUST be before OpenAI client init) ----
import os, sys
from textwrap import dedent   # used for the demo user_query at bottom

# NOTE: storing keys in code is risky; prefer env vars in production.
os.environ["OPENAI_API_KEY"] = "<your-api-key>"
# >>> Replace the literal above with an environment-injected secret in production.

# ---- ensure local folder is importable ----
THIS_DIR = os.path.dirname(__file__)
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)
# -------------------------------------------

import asyncio
import logging
import json
from dataclasses import dataclass, field
from typing import Dict, List, Any
import glob
import re
import shutil

from tools import *  # save_contract, save_invariants, save_verified_invariants
from agents import Agent, Runner, function_tool, handoff
from openai import OpenAI
from z3_checker import Z3Checker                  # noqa: F401
from invariant_autogen import generate_invariants # noqa: F401
from invguard_adapter import run_invguard_core, InvGuardResult

# -------------------------------
# OpenAI client & models
# -------------------------------
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
model_1 = "<your-model>"
model_2 = "<your-model>"

# -------------------------------

# Paths & refinement settings
BASE_EXECUTION_DIR = "/teamspace/studios/this_studio/05_09_25_v4/output_1_v4/test_1"
CORRECT_INVARIANTS_DIR = "/teamspace/studios/this_studio/05_09_25_v4/output_1_v4/test_1_verified_invariants"
MAX_REFINEMENT_ITERATIONS = 3

os.makedirs(BASE_EXECUTION_DIR, exist_ok=True)
os.makedirs(CORRECT_INVARIANTS_DIR, exist_ok=True)

# -------------------------------
# Contract input configuration
# -------------------------------
# Default contracts dir (relative to repository): ../contracts (relative to flow_1_files)
CONTRACTS_DIR = os.environ.get(
    "CONTRACTS_DIR",
    os.path.normpath(os.path.join(THIS_DIR, "..", "contracts"))
)
# Optional: pick a specific contract file (absolute or relative)
CONTRACT_FILE = os.environ.get("CONTRACT_FILE", "")

def _find_contract_on_disk() -> str:
    """
    Return path to a contract file selected from CONFIG:
      - If CONTRACT_FILE is set and exists -> returns that
      - Else, look for .sol files in CONTRACTS_DIR and return the first (sorted) one
      - Else, return empty string
    """
    # 1) explicit CONTRACT_FILE
    if CONTRACT_FILE:
        candidate = CONTRACT_FILE
        if not os.path.isabs(candidate):
            candidate = os.path.normpath(os.path.join(THIS_DIR, candidate))
        if os.path.exists(candidate) and os.path.isfile(candidate):
            return candidate
        else:
            raise FileNotFoundError(f"CONTRACT_FILE specified but not found: {candidate}")

    # 2) search CONTRACTS_DIR
    search_dir = CONTRACTS_DIR
    if not os.path.isabs(search_dir):
        search_dir = os.path.normpath(os.path.join(THIS_DIR, search_dir))
    if os.path.isdir(search_dir):
        sols = sorted([os.path.join(search_dir, f) for f in os.listdir(search_dir) if f.lower().endswith(".sol")])
        if sols:
            return sols[0]
    # Not found
    return ""

def _load_contract_to_base(contract_path: str, dest_filename: str = "contract.sol") -> str:
    """
    Copy the selected contract into BASE_EXECUTION_DIR and return destination path.
    """
    if not os.path.exists(contract_path):
        raise FileNotFoundError(f"Contract file not found: {contract_path}")
    dest = os.path.join(BASE_EXECUTION_DIR, dest_filename)
    shutil.copyfile(contract_path, dest)
    logging.info(f"Copied contract {contract_path} -> {dest}")
    return dest

# ---------------------------------
# Data structures for agent context
# ---------------------------------
@dataclass
class Z3CheckerResult:
    verified_invariants: List[str] = field(default_factory=list)
    failed_invariants: List[Dict[str, Any]] = field(default_factory=list)
    trusted_invariants: List[str] = field(default_factory=list)
    report: str = ""

@dataclass
class AgentContext:
    user_query: str
    generated_invariants: List[str] = field(default_factory=list)
    z3_results: Z3CheckerResult = field(default_factory=Z3CheckerResult)
    refinement_iteration: int = 0
    failed_invariants_for_refinement: List[Dict[str, Any]] = field(default_factory=list)

# ----------------------------------------------------
# Tool: call external Z3Checker via the adapter
# (unchanged behavior expects contract under BASE_EXECUTION_DIR)
# ----------------------------------------------------
@function_tool
def z3_checker_tool(
    contract_filename: str = "contract.sol",
    invariants_filename: str = "invariants.txt",
    function_name: str = ""
) -> Z3CheckerResult:
    """
    Verify invariants using the standalone InvGuard/Z3Checker pipeline.
    Requires 'Z3Checker/' folder under flow_1_files/.
    """
    contract_file = os.path.join(BASE_EXECUTION_DIR, contract_filename)
    if not os.path.exists(contract_file):
        sols = sorted(glob.glob(os.path.join(BASE_EXECUTION_DIR, "*.sol")))
        if sols:
            contract_file = sols[0]
    invariants_txt = os.path.join(BASE_EXECUTION_DIR, invariants_filename)
    z3_root = os.path.join(os.path.dirname(__file__), "Z3Checker")

    if not os.path.exists(contract_file):
        raise FileNotFoundError(f"Contract file not found: {contract_file}")
    if not os.path.exists(invariants_txt):
        raise FileNotFoundError(f"Invariants file not found: {invariants_txt}")
    if not os.path.isdir(z3_root):
        raise FileNotFoundError(f"Z3Checker folder not found: {z3_root}")

    with open(invariants_txt, "r", encoding="utf-8") as f:
        all_lines = [ln.strip() for ln in f if ln.strip()]

    # --- SANITIZER / NORMALIZER ---
    def sanitize(inv: str) -> str:
        s = inv
        s = re.sub(r"\bmsg\.sender\b", "meta.sender", s)
        s = re.sub(r"\bmsg\.value\b", "meta.value", s)
        s = re.sub(r"\bpost_", "post.", s)
        s = re.sub(r"\bpre_", "pre.", s)
        s = re.sub(r"\barg\.arg\.", "arg.", s)   # fix accidental arg.arg.amount
        return s

    all_lines = [sanitize(ln) for ln in all_lines]

    # 🚫 Drop invariants that reference ops the DSL cannot encode
    BANNED_TOKENS = (
        "selfdestruct",      # not a state predicate
        "payable(",          # call-site syntax, not part of DSL
        "delegatecall",
        "staticcall",
        "call(",             # low-level calls
        "call.value",
    )
    def is_supported(line: str) -> bool:
        low = line.replace(" ", "").lower()
        return not any(tok in low for tok in BANNED_TOKENS)

    filtered = [ln for ln in all_lines if is_supported(ln)]
    dropped  = [ln for ln in all_lines if not is_supported(ln)]
    if dropped:
        print("[SANITIZE] Dropping unsupported invariants:")
        for d in dropped:
            print("  -", d)
    all_lines = filtered

    # ---- STRICT PARTITIONING (no arg.* in deposit) ----
    def has_meta_value(s: str) -> bool:
        return "meta.value" in s.lower()

    def has_arg_any(s: str) -> bool:
        return re.search(r"\barg\.", s, flags=re.I) is not None

    deposit_invs, withdraw_invs, neutral_invs = [], [], []
    for inv in all_lines:
        mv = has_meta_value(inv)
        aa = has_arg_any(inv)
        if mv and not aa:
            deposit_invs.append(inv)
        elif aa and not mv:
            withdraw_invs.append(inv)
        elif not mv and not aa:
            neutral_invs.append(inv)
        else:
            # If mentions BOTH, prefer withdraw to keep deposit clean
            withdraw_invs.append(inv)

    # Final line sets for each function
    dep_lines = deposit_invs + neutral_invs
    wdr_lines = withdraw_invs + neutral_invs

    # Belt & suspenders: ensure NO arg.* leaked to deposit
    dep_lines = [x for x in dep_lines if not has_arg_any(x)]

    # Remove stale filtered files to avoid reusing old content
    try:
        for p in glob.glob(os.path.join(BASE_EXECUTION_DIR, "invariants.*.filtered.txt")):
            os.remove(p)
    except Exception:
        pass

    dep_path = os.path.join(BASE_EXECUTION_DIR, "invariants.deposit.filtered.txt")
    wdr_path = os.path.join(BASE_EXECUTION_DIR, "invariants.withdraw.filtered.txt")
    if dep_lines:
        with open(dep_path, "w", encoding="utf-8") as f:
            f.write("\n".join(dep_lines) + "\n")
    if wdr_lines:
        with open(wdr_path, "w", encoding="utf-8") as f:
            f.write("\n".join(wdr_lines) + "\n")

    run_queue = []
    if function_name:
        fn = function_name.strip()
        if fn == "deposit" and dep_lines:
            run_queue.append(("deposit", dep_path))
        elif fn == "withdraw" and wdr_lines:
            run_queue.append(("withdraw", wdr_path))
        else:
            if dep_lines:  run_queue.append(("deposit", dep_path))
            if wdr_lines: run_queue.append(("withdraw", wdr_path))
    else:
        if dep_lines:  run_queue.append(("deposit", dep_path))
        if wdr_lines: run_queue.append(("withdraw", wdr_path))
        if not run_queue:
            run_queue.append((None, invariants_txt))

    merged_verified, merged_failed, merged_trusted, report_lines = [], [], [], []

    for fn, inv_path in run_queue:
        print(f"[DEBUG] Running InvGuard on function={fn}, invariants={inv_path}")
        core: InvGuardResult = run_invguard_core(
            z3checker_root=z3_root,
            contract_path=contract_file,
            invariants_txt_path=inv_path,
            function_name=fn
        )

        merged_verified.extend(core.verified or [])
        merged_failed.extend(core.failed or [])
        merged_trusted.extend(core.trusted or [])

        suffix = f".{fn}" if fn else ""
        per_report = os.path.join(BASE_EXECUTION_DIR, f"z3_validation_report{suffix}.txt")
        with open(per_report, "w", encoding="utf-8") as f:
            f.write("\n".join(core.report_lines))
        report_lines.append(f"[{fn or 'all'}]\n" + "\n".join(core.report_lines))

    only_trusted = bool(merged_trusted) and not merged_verified and not merged_failed
    if only_trusted:
        report_lines.insert(0, "[only_trusted] no verified/failures; likely checker fallback or unsupported inputs")

    combined_report = os.path.join(BASE_EXECUTION_DIR, "z3_validation_report.txt")
    with open(combined_report, "w", encoding="utf-8") as f:
        f.write("\n\n".join(report_lines))

    # ✅ WRITE the aggregate verified/trusted to the CORRECT_INVARIANTS_DIR (final destination)
    save_verified_invariants(
        merged_verified,
        merged_trusted,
        out_dir=CORRECT_INVARIANTS_DIR,
        filename="verified_invariants.txt",
    )

    if not merged_verified and not merged_failed and not merged_trusted:
        crash_report = os.path.join(BASE_EXECUTION_DIR, "z3_validation_report.crash.txt")
        with open(crash_report, "w", encoding="utf-8") as f:
            f.write("\n\n".join(report_lines))
        raise RuntimeError("Z3Checker failed (no results). See crash report.")

    return Z3CheckerResult(
        verified_invariants=merged_verified,
        failed_invariants=merged_failed,
        trusted_invariants=merged_trusted,
        report="\n\n".join(report_lines),
    )

# ----------------------------------------------------
# Agents
# ----------------------------------------------------
z3_checker_agent = Agent[AgentContext](
    name="z3_checker_agent",
    instructions=f"""
You are an expert verification specialist using the external InvGuard/Z3Checker pipeline.

Process:
1) Call z3_checker_tool to verify invariants in BASE_EXECUTION_DIR.
2) Summarize VERIFIED / FAILED / TRUSTED and include counterexamples when present.
3) Populate context.failed_invariants_for_refinement with any failures.
4) If some fail and context.refinement_iteration < {MAX_REFINEMENT_ITERATIONS}, hand off to the refiner.
   Otherwise, finish and write the final summary.
""",
    model=model_2,
    tools=[z3_checker_tool],
    handoffs=[]
)

invariant_refiner_agent = Agent[AgentContext](
    name="invariant_refiner_agent",
    instructions=f"""
Refine failed invariants using checker counterexamples, then re-run Z3 automatically.

STRICT FORMAT (no comments, one per line):
- Use ONLY: pre.X, post.X, meta.sender, meta.value, arg.Y
- Mappings: select(pre.m, K) / select(post.m, K)
- Allowed ops: and, or, not, =>, ==, !=, >=, <=, >, <, +, -, *
""",
    model=model_1,
    tools=[save_invariants, z3_checker_tool],
    handoffs=[]
)

invariant_generating_agent = Agent[AgentContext](
    name="invariant_generating_agent",
    instructions=""" 
Analyze the Solidity contract, generate invariants, save them, then hand off to z3_checker_agent.

STRICT OUTPUT RULES (no commentary, raw lines only):
- Use ONLY this DSL:
  * pre.X, post.X
  * meta.sender, meta.value
  * arg.<name>
  * select(pre.m, key) / select(post.m, key)
- No old(), now, timestamp, arrays, msg.*.
- Examples:
  meta.value > 0 => select(post.balances, meta.sender) == select(pre.balances, meta.sender) + meta.value
  select(post.balances, meta.sender) >= 0
""",
    model=model_1,
    tools=[save_contract, save_invariants],
    handoffs=[]
)

# Handoffs
z3_checker_agent_handoff = handoff(agent=z3_checker_agent)
invariant_refiner_agent_handoff = handoff(agent=invariant_refiner_agent)
invariant_generating_agent_handoff = handoff(agent=invariant_generating_agent)

z3_checker_agent.handoffs = [invariant_refiner_agent_handoff]
invariant_refiner_agent.handoffs = [z3_checker_agent_handoff]
invariant_generating_agent.handoffs = [z3_checker_agent_handoff]  # keep for completeness (not used directly)

orchestrator_agent = Agent[AgentContext](
    name="orchestrator_agent",
    instructions="Take user query (contract) → invariant generator → checker → (refiner ↔ checker) until done.",
    model=model_2,
    tools=[],
    handoffs=[invariant_generating_agent_handoff]
)

# -------------------------------
# Entry point
# -------------------------------
async def main():
    logging.basicConfig(level=logging.INFO)

    # First: try to detect a contract file from the shared contracts folder (or CONTRACT_FILE).
    contract_on_disk = ""
    try:
        contract_on_disk = _find_contract_on_disk()
    except Exception as e:
        logging.error(f"Error locating contract: {e}")
        # Keep contract_on_disk empty; we'll error below if needed.

    contract_source_text = ""
    if contract_on_disk:
        # Copy contract into BASE_EXECUTION_DIR so downstream tools find it
        try:
            _load_contract_to_base(contract_on_disk, dest_filename="contract.sol")
            with open(os.path.join(BASE_EXECUTION_DIR, "contract.sol"), "r", encoding="utf-8") as f:
                contract_source_text = f.read()
            logging.info(f"Loaded contract text from {contract_on_disk}")
        except Exception as e:
            logging.exception(f"Failed to stage contract into BASE_EXECUTION_DIR: {e}")
            raise
    else:
        # No disk contract located. For backward compatibility: you can choose to
        # fall back to a bundled inline contract, or error out. We will error out
        # to avoid silently using incorrect input.
        raise FileNotFoundError(
            "No contract file found. Place a .sol in CONTRACTS_DIR "
            f"({CONTRACTS_DIR}), or set CONTRACT_FILE to a specific path."
        )

    # Build the user_query used by the invariant generator/agents.
    # This keeps the exact same format as earlier (triple-backtick solidity block).
    user_query = dedent(f"""\
        Please analyze the following Solidity smart contract and generate invariants for it:

        ```solidity
        {contract_source_text}
        ```
    """)

    agent_run_context = AgentContext(user_query=user_query)
    run_outcome = await Runner.run(
        orchestrator_agent,
        user_query,
        context=agent_run_context,
        max_turns=12
    )
    print("Run outcome:", run_outcome)

if __name__ == "__main__":
    asyncio.run(main())
