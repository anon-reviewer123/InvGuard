# flow_2_files/agent.py
# ---- set OpenAI API key (MUST be before OpenAI client init) ----
import os
import sys
os.environ["OPENAI_API_KEY"] = "<your-api-key>"
# >>> Replace the literal above with an environment-injected secret in production.

# ---- ensure local folder is importable ----
THIS_DIR = os.path.dirname(__file__)
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)
# -------------------------------------------

import asyncio
import logging
import time
import difflib
import re
from dataclasses import dataclass
from typing import Tuple, List, Dict
from openai import OpenAI
from datetime import datetime
import json
import glob

# Agents library imports
from agents import Agent, Runner, function_tool, handoff, ModelSettings

# ---------------------------
# OpenAI client & models
# ---------------------------
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# Use your provided models
model_1 = "<your-model>"  # Attack, Fix Maker, Fix Checker
model_2 = "<your-model>"                                           # Orchestrator

# IMPORTANT: output dir
BASE_EXECUTION_DIR = os.environ.get(
    "BASE_EXECUTION_DIR",
    "/teamspace/studios/this_studio/05_09_25_v4/output_1_v4/flow2_output"
)
os.makedirs(BASE_EXECUTION_DIR, exist_ok=True)

# ---------------------------
# Shared input locations (same as flow 1)
# ---------------------------
CONTRACTS_DIR = "/teamspace/studios/this_studio/InvGuard/InvGuard/InvGuard/contracts"
INVARIANTS_PATH = "/teamspace/studios/this_studio/05_09_25_v4/output_1_v4/test_1_verified_invariants/verified_invariants.txt"

def _load_contract_text() -> str:
    """
    Load the first *.sol file from CONTRACTS_DIR (sorted), or raise a clear error.
    """
    if not os.path.isdir(CONTRACTS_DIR):
        raise FileNotFoundError(f"Contracts dir not found: {CONTRACTS_DIR}")
    sols = sorted(glob.glob(os.path.join(CONTRACTS_DIR, "*.sol")))
    if not sols:
        raise FileNotFoundError(f"No .sol files found in {CONTRACTS_DIR}")
    path = sols[0]
    with open(path, "r", encoding="utf-8") as f:
        src = f.read().strip()
    logging.info(f"Loaded input contract from {path}")
    return src

# ---------------------------
# Tools
# ---------------------------
@function_tool
def save_exploit_analysis(contract_code: str, vulnerabilities: str, exploit_details: str) -> str:
    exploits_dir = os.path.join(BASE_EXECUTION_DIR, "exploit_analysis")
    os.makedirs(exploits_dir, exist_ok=True)

    timestamp = time.strftime('%Y%m%d-%H%M%S')
    filename = f"exploit_analysis_{timestamp}.txt"
    filepath = os.path.join(exploits_dir, filename)
    try:
        with open(filepath, "w", encoding='utf-8') as f:
            f.write("Exploit Analysis Report\n")
            f.write(f"Generated At: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("=" * 80 + "\n")
            f.write("ORIGINAL CONTRACT CODE\n")
            f.write("=" * 80 + "\n")
            f.write(f"{contract_code}\n\n")
            f.write("=" * 80 + "\n")
            f.write("VULNERABILITIES FOUND\n")
            f.write("=" * 80 + "\n")
            f.write(f"{vulnerabilities}\n\n")
            f.write("=" * 80 + "\n")
            f.write("EXPLOIT DETAILS\n")
            f.write("=" * 80 + "\n")
            f.write(f"{exploit_details}\n")
        logging.info(f"Exploit analysis saved to {filepath}")
        return filepath
    except Exception as e:
        logging.error(f"Error saving exploit analysis: {e}")
        return f"Error: {e}"

@function_tool
def save_attack_candidate(candidate_id: str, contract_code: str, title: str, severity: str, description: str, poc_steps: str, invariants_violated: str) -> str:
    out_dir = os.path.join(BASE_EXECUTION_DIR, "exploit_analysis", "candidates")
    os.makedirs(out_dir, exist_ok=True)
    safe_id = candidate_id.replace(" ", "_")
    filename = f"attack_candidate_{safe_id}.txt"
    path = os.path.join(out_dir, filename)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"Candidate ID: {candidate_id}\n")
            f.write(f"Title: {title}\n")
            f.write(f"Severity: {severity}\n\n")
            f.write("DESCRIPTION\n")
            f.write("-----------\n")
            f.write(description.strip() + "\n\n")
            f.write("POC STEPS\n")
            f.write("---------\n")
            f.write(poc_steps.strip() + "\n\n")
            f.write("INVARIANTS VIOLATED\n")
            f.write("-------------------\n")
            f.write(invariants_violated.strip() + "\n\n")
            f.write("CONTRACT\n")
            f.write("--------\n")
            f.write(contract_code)
        logging.info(f"Saved attack candidate to {path}")
        return path
    except Exception as e:
        logging.error(f"save_attack_candidate error: {e}")
        return f"error: {e}"

@function_tool
def save_final_fix(original_contract: str, fixed_contract: str, fix_description: str, invariants_used: str) -> str:
    fixes_dir = os.path.join(BASE_EXECUTION_DIR, "approved_fixes")
    os.makedirs(fixes_dir, exist_ok=True)

    timestamp = time.strftime('%Y%m%d-%H%M%S')
    base_name = f"approved_fix_{timestamp}"
    txt_filepath = os.path.join(fixes_dir, f"{base_name}.txt")
    orig_sol_path = os.path.join(fixes_dir, f"{base_name}.original.sol")
    fixed_sol_path = os.path.join(fixes_dir, f"{base_name}.fixed.sol")
    diff_path = os.path.join(fixes_dir, f"{base_name}.diff")

    try:
        with open(txt_filepath, "w", encoding='utf-8') as f:
            f.write("Approved Smart Contract Fix\n")
            f.write(f"Generated At: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("=" * 80 + "\n")
            f.write("FIX DESCRIPTION\n")
            f.write("=" * 80 + "\n")
            f.write(f"{fix_description}\n\n")
            f.write("=" * 80 + "\n")
            f.write("INVARIANTS CONSIDERED\n")
            f.write("=" * 80 + "\n")
            f.write(f"{invariants_used}\n\n")
            f.write("=" * 80 + "\n")
            f.write("ORIGINAL CONTRACT\n")
            f.write("=" * 80 + "\n")
            f.write(f"{original_contract}\n\n")
            f.write("=" * 80 + "\n")
            f.write("FIXED CONTRACT\n")
            f.write("=" * 80 + "\n")
            f.write(f"{fixed_contract}\n")

        with open(orig_sol_path, "w", encoding="utf-8") as f:
            f.write(original_contract)
        with open(fixed_sol_path, "w", encoding="utf-8") as f:
            f.write(fixed_contract)

        orig_lines = original_contract.splitlines(keepends=True)
        fixed_lines = fixed_contract.splitlines(keepends=True)
        diff_lines = list(difflib.unified_diff(
            orig_lines, fixed_lines,
            fromfile=os.path.basename(orig_sol_path),
            tofile=os.path.basename(fixed_sol_path),
            lineterm=""
        ))
        with open(diff_path, "w", encoding="utf-8") as f:
            if diff_lines:
                f.write("\n".join(diff_lines) + "\n")
            else:
                f.write("# No differences found (diff empty)\n")

        logging.info(f"Final fix saved to {txt_filepath}")
        logging.info(f"Wrote artifacts: {orig_sol_path}, {fixed_sol_path}, {diff_path}")
        return txt_filepath
    except Exception as e:
        logging.error(f"Error saving final fix: {e}")
        return f"Error: {e}"

@function_tool
def check_fix_diff(original_contract: str, fixed_contract: str) -> str:
    fixes_dir = os.path.join(BASE_EXECUTION_DIR, "approved_fixes")
    os.makedirs(fixes_dir, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    base_name = f"fix_check_{timestamp}"
    orig_sol_path = os.path.join(fixes_dir, f"{base_name}.original.sol")
    fixed_sol_path = os.path.join(fixes_dir, f"{base_name}.fixed.sol")
    diff_path = os.path.join(fixes_dir, f"{base_name}.diff")

    try:
        def normalize(s: str):
            return "\n".join(line.rstrip() for line in s.splitlines())

        orig_norm = normalize(original_contract)
        fixed_norm = normalize(fixed_contract)

        with open(orig_sol_path, "w", encoding="utf-8") as f:
            f.write(orig_norm + "\n")
        with open(fixed_sol_path, "w", encoding="utf-8") as f:
            f.write(fixed_norm + "\n")

        orig_lines = orig_norm.splitlines(keepends=True)
        fixed_lines = fixed_norm.splitlines(keepends=True)
        diff_lines = list(difflib.unified_diff(
            orig_lines, fixed_lines,
            fromfile=os.path.basename(orig_sol_path),
            tofile=os.path.basename(fixed_sol_path),
            lineterm=""
        ))

        with open(diff_path, "w", encoding="utf-8") as f:
            if diff_lines:
                f.write("\n".join(diff_lines) + "\n")
                status = "changed"
            else:
                f.write("# No differences found (diff empty)\n")
                status = "no-change"

        logging.info(f"check_fix_diff: status={status}, diff={diff_path}")
        return f"{status}|{diff_path}"
    except Exception as e:
        logging.error(f"check_fix_diff error: {e}")
        return f"error|{e}"

@function_tool
def check_reentrancy_pattern(contract_code: str) -> str:
    try:
        text = contract_code
        lower = text.lower()

        if "nonreentrant" in lower or "reentrancyguard" in lower:
            return "safe|reason=nonReentrant_or_ReentrancyGuard"

        m = re.search(
            r"function\s+withdraw\s*\([^)]*\)\s*(?:public|external|internal|private|payable|view|pure|\s)*[^{]*\{([\s\S]*?)\}",
            text, re.IGNORECASE
        )
        if not m:
            m2 = re.search(r"function\s+withdraw\s*\([^)]*\)\s*{([\s\S]*?)\}", text, re.IGNORECASE)
            if not m2:
                return "error|reason=withdraw_not_found"
            body = m2.group(1)
        else:
            body = m.group(1)

        state_update = re.search(r"balances\s*\[\s*msg\.sender\s*\]\s*-\=\s*amount\s*;", body, re.IGNORECASE)
        if not state_update:
            state_update = re.search(
                r"balances\s*\[\s*msg\.sender\s*\]\s*=\s*balances\s*\[\s*msg\.sender\s*\]\s*-\s*amount\s*;",
                body, re.IGNORECASE
            )

        external_call = re.search(r"\.\s*(transfer|send|call)\s*\(", body, re.IGNORECASE)

        if not external_call:
            if state_update:
                return "safe|reason=no_external_calls_in_withdraw"
            else:
                return "unsafe|reason=no_external_calls_and_no_state_update_found"

        if state_update and external_call:
            if state_update.start() < external_call.start():
                return "safe|reason=CEI_order_state_before_external_call"
            else:
                return "unsafe|reason=external_call_before_state_update"

        if external_call and not state_update:
            return "unsafe|reason=external_call_without_detected_state_decrement"

        return "unsafe|reason=unable_to_confirm_safety"
    except Exception as e:
        return f"error|reason={e}"

@function_tool
def check_candidate_coverage(candidate_json_str: str, coverage_text: str) -> str:
    try:
        candidates = json.loads(candidate_json_str)
        ids = []
        if isinstance(candidates, list):
            for it in candidates:
                if isinstance(it, dict) and "id" in it:
                    ids.append(str(it["id"]))
        elif isinstance(candidates, dict):
            ids = list(candidates.keys())
        else:
            return "error|reason=candidates_not_list_or_obj"

        missing = [i for i in ids if re.search(rf"\b{i}\b", coverage_text) is None]
        if missing:
            return f"missing|reason=ids_missing:{','.join(missing)}"

        issues = []
        for it in candidates if isinstance(candidates, list) else []:
            cid = it.get("id")
            sev = 0
            try:
                sev = int(it.get("severity", 0))
            except:
                pass
            if sev >= 7:
                m = re.search(rf"{re.escape(str(cid))}(.{{0,200}})", coverage_text, re.IGNORECASE)
                snippet = m.group(1) if m else coverage_text
                if re.search(r"(nonReentrant|ReentrancyGuard|checks-effects-interactions|cei|onlyOwner|mutex|limit|cooldown|SafeMath|overflow|underflow)", snippet, re.IGNORECASE) is None:
                    issues.append(f"{cid}:no_concrete_mitigation")

        if issues:
            return f"insufficient|reason={';'.join(issues)}"
        return "ok|reason=all_covered"
    except Exception as e:
        return f"error|reason={e}"

@function_tool
def save_fix_candidate(candidate_name: str, original_contract: str, fixed_contract: str, notes: str) -> str:
    drafts_dir = os.path.join(BASE_EXECUTION_DIR, "approved_fixes", "drafts")
    os.makedirs(drafts_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", candidate_name)[:80]
    txt_path = os.path.join(drafts_dir, f"{safe_name}_{ts}.txt")
    orig_sol_path = os.path.join(drafts_dir, f"{safe_name}_{ts}.original.sol")
    fixed_sol_path = os.path.join(drafts_dir, f"{safe_name}_{ts}.fixed.sol")
    try:
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"Fix Draft: {candidate_name}\n")
            f.write(f"Saved At: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("NOTES\n")
            f.write("-----\n")
            f.write(notes.strip() + "\n\n")
            f.write("ORIGINAL CONTRACT\n")
            f.write("---------------\n")
            f.write(original_contract + "\n\n")
            f.write("PROPOSED FIX (FULL SOURCE)\n")
            f.write("--------------------------\n")
            f.write(fixed_contract + "\n")
        with open(orig_sol_path, "w", encoding="utf-8") as f:
            f.write(original_contract)
        with open(fixed_sol_path, "w", encoding="utf-8") as f:
            f.write(fixed_contract)
        logging.info(f"Saved fix candidate to {txt_path}")
        return txt_path
    except Exception as e:
        logging.error(f"save_fix_candidate error: {e}")
        return f"error:{e}"

# ---------------------------
# Agent context dataclass
# ---------------------------
@dataclass
class AgentContext:
    user_query: str
    contract_code: str = ""
    invariants_file_path: str = ""
    exploit_analysis_path: str = ""
    proposed_fix: str = ""
    fix_description: str = ""
    invariants_used: str = ""
    attack_candidates: List[Dict[str, str]] = None
    attack_reports_dir: str = ""

# ---------------------------
# Agents (instructions unchanged)
# ---------------------------
attack_module_agent = Agent[AgentContext](
    name="attack_module_agent",
    instructions="""
You are the Attack Module Agent — a smart-contract offensive analyst.

GOAL:
  - Generate exactly **5 distinct attack candidates** (A1..A5).
  - Save each candidate with save_attack_candidate.
  - Output them as a raw JSON array (no backticks, no markdown).

STRICT RULES:
  - Never wrap JSON in ```json or ``` fences.
  - Always save all 5 candidates with save_attack_candidate(...).
""",
    model=model_1,
    tools=[save_attack_candidate, save_exploit_analysis],
    handoffs=[]
)

fix_maker_agent = Agent[AgentContext](
    name="fix_maker_agent",
    instructions="""
You are the Fix Maker Agent — produce a single, cohesive, **compilable** Solidity file that mitigates the provided attack candidates and preserves the given invariants.

MANDATORY (strict):
1. **Output must be valid, compilable Solidity ^0.8.0**. If you use any modifier or symbol (e.g. `nonReentrant`), include import/inheritance or implement a local mutex.
2. Introduce at least one real code-level security change.
3. Do not return the original contract unchanged.

OUTPUT FORMAT:
FIXED_CONTRACT_START
<entire solidity source>
FIXED_CONTRACT_END

CANDIDATE_COVERAGE_START
{ "A1":"...", "A2":"...", "A3":"...", "A4":"...", "A5":"..." }
CANDIDATE_COVERAGE_END

FIX_DESCRIPTION:
<2–6 sentences>
""",
    model=model_1,
    tools=[save_fix_candidate],
    handoffs=[]
)

fix_checker_agent = Agent[AgentContext](
    name="fix_checker_agent",
    instructions="""
You are the Fix Checker.

Steps:
1) Parse FIXED_CONTRACT and CANDIDATE_COVERAGE.
2) Run check_fix_diff -> must be "changed".
3) If a reentrancy candidate exists, run check_reentrancy_pattern -> must be safe.
4) Run check_candidate_coverage -> must be ok.
5) If any step fails, REJECT and hand back to FixMaker.
6) If all pass, call save_final_fix and APPROVE.
""",
    model=model_1,
    tools=[save_final_fix, check_fix_diff, check_reentrancy_pattern, check_candidate_coverage],
    handoffs=[]
)

# ---------------------------
# Handoffs wiring
# ---------------------------
attack_module_agent_handoff = handoff(agent=attack_module_agent)
fix_maker_agent_handoff    = handoff(agent=fix_maker_agent)
fix_checker_agent_handoff  = handoff(agent=fix_checker_agent)

attack_module_agent.handoffs = [fix_maker_agent_handoff]
fix_maker_agent.handoffs    = [fix_checker_agent_handoff]
fix_checker_agent.handoffs  = [fix_maker_agent_handoff]  # loop if needed

# keep tool lists clean (no Handoff objects inside .tools)
attack_module_agent.tools = [save_attack_candidate, save_exploit_analysis]
fix_maker_agent.tools     = [save_fix_candidate]
fix_checker_agent.tools   = [save_final_fix, check_fix_diff, check_reentrancy_pattern, check_candidate_coverage]

# ---------------------------
# Orchestrator Agent
# ---------------------------
orchestrator_agent = Agent[AgentContext](
    name="orchestrator_agent",
    instructions="You are the Orchestrator Agent. Extract contract and invariants and handoff to attack_module_agent.",
    model=model_2,
    tools=[],
    handoffs=[attack_module_agent_handoff]
)

orchestrator_agent.model_settings = ModelSettings(tool_choice="auto")
attack_module_agent.model_settings = ModelSettings(tool_choice="auto")
fix_maker_agent.model_settings = ModelSettings(tool_choice="auto")
fix_checker_agent.model_settings = ModelSettings(tool_choice="auto")

# ---------------------------
# Helpers
# ---------------------------
def _extract_invariants_and_contract(user_query: str) -> Tuple[str, str]:
    invariants_path = ""
    contract_code = user_query

    for line in user_query.splitlines():
        if line.strip().lower().startswith("invariants file:"):
            invariants_path = line.split(":", 1)[1].strip()
            break

    m = re.search(r"```(?:solidity)?\s*(.*?)\s*```", user_query, re.S | re.I)
    if m:
        contract_code = m.group(1).strip()
    else:
        m2 = re.search(r"<solidity>(.*?)</solidity>", user_query, re.S | re.I)
        if m2:
            contract_code = m2.group(1).strip()

    return invariants_path, contract_code

# ---------------------------
# Main
# ---------------------------
async def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Load the shared input contract (same as flow 1)
    contract_src = _load_contract_text()

    # Build user_query dynamically (no Solidity hardcoded here)
    user_query = f"""
Please analyze and fix the following smart contract. 
Invariants file: {INVARIANTS_PATH}
```solidity
{contract_src}
```"""

    print("Starting smart contract fix generation workflow...")
    os.makedirs(BASE_EXECUTION_DIR, exist_ok=True)
    print(f"Results will be saved in: {BASE_EXECUTION_DIR}/")

    invariants_path, contract_code = _extract_invariants_and_contract(user_query)

    # Build context
    agent_run_context = AgentContext(
        user_query=user_query,
        contract_code=contract_code,
        invariants_file_path=invariants_path
    )

    # Load VERIFIED invariants file content into context so agents can use it
    if invariants_path:
        try:
            if os.path.exists(invariants_path):
                with open(invariants_path, "r", encoding="utf-8") as f:
                    inv_text = f.read().strip()
                agent_run_context.invariants_used = inv_text
                line_count = len(inv_text.splitlines()) if inv_text else 0
                print(f"Loaded invariants from: {invariants_path}  (lines: {line_count})")
            else:
                print(f"WARNING: Invariants file not found at: {invariants_path}")
        except Exception as e:
            print(f"WARNING: Failed to read invariants file: {e}")

    try:
        run_outcome = await Runner.run(
            orchestrator_agent,
            user_query,
            context=agent_run_context,
            max_turns=30
        )
        print("\nWorkflow completed!")
        if run_outcome:
            print(f"Final outcome: {run_outcome}")
    except Exception as e:
        logging.exception("An error occurred during the workflow execution")
        print(f"ERROR: {e}")

    print(f"\nResults saved in: {BASE_EXECUTION_DIR}/")
    print("- exploit_analysis/ - Security analysis results")
    print("- approved_fixes/ - Final approved fixes")

if __name__ == "__main__":
    asyncio.run(main())
