# flow_1_files/invguard_adapter.py
import sys
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional


class InvGuardResult:
    def __init__(self):
        self.verified: List[str] = []
        self.failed: List[Dict[str, Any]] = []
        self.trusted: List[str] = []
        self.report_lines: List[str] = []


def _sanitize_invariant(line: str) -> str:
    """Clean up common formatting mistakes in generated invariants."""
    # Remove accidental double closing parentheses
    while ")))" in line:
        line = line.replace(")))", "))")
    # Fix cases like select(...)) at the end
    if line.endswith("))") and not line.endswith("(())"):
        line = line[:-1]
    # Strip extra spaces
    line = line.strip()
    return line


def run_invguard_core(
    z3checker_root: str,
    contract_path: str,
    invariants_txt_path: str,
    function_name: Optional[str] = None
) -> InvGuardResult:
    cmd = [sys.executable, "-m", "cli.driver", contract_path]
    if function_name:
        cmd += ["-f", function_name]
    cmd += ["--llm-invariants", invariants_txt_path]

    # NEW: visible launch log
    print(f"[ADAPTER] launching: {' '.join(cmd)} (cwd={z3checker_root})")

    proc = subprocess.run(cmd, cwd=z3checker_root, capture_output=True, text=True)

    # NEW: visible outcome logs
    print(f"[ADAPTER] returncode={proc.returncode}")
    if proc.stderr:
        lines = proc.stderr.strip().splitlines()
        head = "\n".join(lines[:60])  # print first 60 lines to keep console readable
        print(f"[ADAPTER] stderr (head):\n{head}\n{'[... truncated ...]' if len(lines) > 60 else ''}")

    result = InvGuardResult()
    out_lines = (proc.stdout or "").splitlines()
    err = proc.stderr or ""

    # Always capture stdout into report
    result.report_lines.append(f"[adapter] cmd: {' '.join(cmd)}")
    result.report_lines.append(f"[adapter] cwd: {z3checker_root}")
    result.report_lines.append(f"[adapter] returncode: {proc.returncode}")
    result.report_lines += out_lines

    # Hard fail if Z3Checker crashed
    if proc.returncode != 0:
        if err.strip():
            result.report_lines.append("[adapter] STDERR:")
            result.report_lines.append(err.strip())
        raise RuntimeError(
            f"Z3Checker failed with return code {proc.returncode}. "
            f"See report_lines for details."
        )

    # Normal parse on success (sanitize invariants as we load them)
    raw_lines = [
        _sanitize_invariant(l.strip())
        for l in Path(invariants_txt_path).read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    idx = 0
    for ln in out_lines:
        s = ln.strip()
        if s:
            result.report_lines.append(s)
        if s.startswith("- inv_"):
            idx += 1
            raw = raw_lines[idx - 1] if idx - 1 < len(raw_lines) else f"<inv_{idx}>"
            if "HOLDS" in s:
                result.verified.append(raw)
            elif "VIOLATED" in s:
                result.failed.append({"invariant": raw, "counterexample": None})
            else:
                result.trusted.append(raw)
        elif s.startswith("  Counterexample:") and result.failed:
            ce = s.split("Counterexample:", 1)[1].strip()
            if not result.failed[-1]["counterexample"]:
                result.failed[-1]["counterexample"] = ce

    # ✅ FINAL clear summary in terminal
    print("\n=== [ADAPTER] FINAL INVARIANT SUMMARY ===")
    print("✅ Verified invariants:")
    for inv in result.verified:
        print("   -", inv)
    print("❌ Violated invariants:")
    for f in result.failed:
        print("   -", f["invariant"], f"(CE: {f['counterexample']})")
    print("🤝 Trusted invariants:")
    for inv in result.trusted:
        print("   -", inv)
    print("========================================\n")

    # ✅ Write verified + trusted invariants to a per-function file
    if function_name:
        out_file = Path(contract_path).parent / f"verified_invariants.{function_name}.txt"
    else:
        out_file = Path(contract_path).parent / "verified_invariants.global.txt"

    with open(out_file, "w", encoding="utf-8") as f:
        if result.verified:
            f.write("# VERIFIED INVARIANTS\n")
            for inv in result.verified:
                f.write(inv + "\n")
        if result.trusted:
            f.write("\n# TRUSTED INVARIANTS\n")
            for inv in result.trusted:
                f.write(inv + "\n")

    print(f"[ADAPTER] Verified/Trusted invariants written to {out_file}")

    return result
