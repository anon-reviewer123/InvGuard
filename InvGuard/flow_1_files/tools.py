# flow_1_files/tools.py
from agents import function_tool
from typing import List, Tuple
import os
import re
from pathlib import Path

# ==============================
# Base execution directory (ONE source of truth)
#   All Flow-1 artifacts will be written here:
#   - contract.sol
#   - invariants.txt  (normalized DSL format for Z3Checker)
#   - z3_validation_report*.txt (written by the checker tool)
# ==============================
BASE_EXECUTION_DIR = "/teamspace/studios/this_studio/05_09_25_v4/output_1_v4/test_1"

# ------------------------------
# Normalizer helpers
# ------------------------------
_unicode_ops = {
    "⇒": "=>",
    "→": "=>",
    "≥": ">=",
    "≤": "<=",
    "≠": "!=",
    "—": "-",
    "–": "-",
}

def _replace_unicode_ops(s: str) -> str:
    for bad, good in _unicode_ops.items():
        s = s.replace(bad, good)
    return s

def normalize_invariant_line(s: str) -> str:
    """
    Rewrite an invariant string into the restricted DSL expected by Z3Checker.

    Key rewrites:
      - msg.sender/value -> meta.sender/value
      - amount -> arg.amount
      - balances[KEY] -> select(post.balances, KEY)   (fallback if no pre/post)
      - pre.balances[KEY] / post.balances[KEY] -> select(pre|post.balances, KEY)
      - pre.balances(KEY) / post.balances(KEY) -> select(pre|post.balances, KEY)
      - balances(KEY) -> select(post.balances, KEY)
      - balancer(...) -> balances(...), then normalized
      - normalize implication and comparison operators
    """
    t = (s or "").strip()

    # Trim bullets / code fences / trailing punctuation that sneak in
    t = t.strip("`•*- \t")
    t = _replace_unicode_ops(t)
    t = t.replace("->", "=>")

    # msg.* → meta.*
    t = re.sub(r"\bmsg\.sender\b", "meta.sender", t)
    t = re.sub(r"\bmsg\.value\b", "meta.value", t)

    # Fix amount → arg.amount (standalone token)
    t = re.sub(r"\bamount\b", "arg.amount", t)

    # Common typos
    t = t.replace("balancer", "balances")

    # Underscore variants to dotted
    t = t.replace("pre_balances", "pre.balances")
    t = t.replace("post_balances", "post.balances")
    t = t.replace("pre_balance", "pre.balances")   # just in case
    t = t.replace("post_balance", "post.balances") # just in case
    t = t.replace("pre.balances.", "pre.balances")   # collapse accidental dot
    t = t.replace("post.balances.", "post.balances") # collapse accidental dot

    # Paren indexing -> select(...)
    t = re.sub(r"(pre|post)\.([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*([^)]+?)\s*\)",
               r"select(\1.\2, \3)", t)

    # Bracket indexing -> select(...)
    t = re.sub(r"pre\.([A-Za-z_][A-Za-z0-9_]*)\s*\[\s*([^\]]+?)\s*\]",
               r"select(pre.\1, \2)", t)
    t = re.sub(r"post\.([A-Za-z_][A-Za-z0-9_]*)\s*\[\s*([^\]]+?)\s*\]",
               r"select(post.\1, \2)", t)

    # Fallbacks without pre/post
    t = re.sub(r"\bbalances\s*\[\s*([^\]]+?)\s*\]", r"select(post.balances, \1)", t)
    t = re.sub(r"\bbalances\s*\(\s*([^)]+?)\s*\)", r"select(post.balances, \1)", t)

    # Very common specific
    t = re.sub(r"\bbalances\s*\(\s*meta\.sender\s*\)", "select(post.balances, meta.sender)", t)

    # Collapse weird spacing around commas inside select
    t = re.sub(r"select\(\s*", "select(", t)
    t = re.sub(r"\s*,\s*", ", ", t)
    t = re.sub(r"\s*\)", ")", t)

    # Final cleanup of multiple spaces
    t = re.sub(r"\s{2,}", " ", t).strip()

    return t

# ------------------------------
# Tools
# ------------------------------
@function_tool
def save_contract(contract_code: str, filename: str = "contract.sol") -> str:
    """
    Save smart contract code to a .sol file in the base execution directory.

    Args:
        contract_code: Solidity contract code
        filename: target filename (default: contract.sol)

    Returns:
        Success/error string with full path
    """
    try:
        os.makedirs(BASE_EXECUTION_DIR, exist_ok=True)
        if not filename.endswith(".sol"):
            filename += ".sol"
        file_path = os.path.join(BASE_EXECUTION_DIR, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(contract_code)
        return f"Smart contract successfully saved to: {file_path}"
    except Exception as e:
        return f"Error saving contract: {e}"

@function_tool
def save_invariants(invariants: List[str], filename: str = "invariants.txt") -> str:
    """
    Save generated invariants to a .txt file in the base execution directory.
    Invariants are passed through a sanitizer/normalizer to enforce the DSL
    supported by Z3Checker (meta.sender, meta.value, arg.amount, select(...)).

    Args:
        invariants: list of invariant strings
        filename: target filename (default: invariants.txt)

    Returns:
        Success/error string with full path
    """
    try:
        os.makedirs(BASE_EXECUTION_DIR, exist_ok=True)
        if not filename.endswith(".txt"):
            filename += ".txt"
        file_path = os.path.join(BASE_EXECUTION_DIR, filename)

        normed: List[str] = []
        for inv in invariants or []:
            clean = (inv or "").strip()
            if clean:
                normed.append(normalize_invariant_line(clean))

        with open(file_path, "w", encoding="utf-8") as f:
            if normed:
                f.write("\n".join(normed) + "\n")
            else:
                f.write("")

        return f"Invariants successfully saved to: {file_path}"
    except Exception as e:
        return f"Error saving invariants: {e}"

# ✅ NEW: this is the bit your agent expects and that controls the final file.
def save_verified_invariants(
    verified: List[str],
    trusted: List[str],
    out_dir: str = None,
    filename: str = "verified_invariants.txt",
) -> str:
    """
    Write ONLY the final verified + trusted invariants to a single file.
    Overwrites the target file each run.

    Args:
        verified: invariants that HOLD
        trusted: invariants that were trusted (no counterexample but not formally proved)
        out_dir: destination directory; defaults to BASE_EXECUTION_DIR if None
        filename: output filename, default 'verified_invariants.txt'

    Returns:
        Full path written
    """
    try:
        if out_dir is None:
            out_dir = BASE_EXECUTION_DIR
        os.makedirs(out_dir, exist_ok=True)
        out_path = Path(out_dir) / filename

        # Normalize lines before writing
        v_norm = [normalize_invariant_line(x) for x in (verified or []) if (x or "").strip()]
        t_norm = [normalize_invariant_line(x) for x in (trusted or []) if (x or "").strip()]

        with open(out_path, "w", encoding="utf-8") as f:
            if v_norm:
                f.write("# VERIFIED INVARIANTS\n")
                for inv in v_norm:
                    f.write(inv + "\n")
            if t_norm:
                if v_norm:
                    f.write("\n")
                f.write("# TRUSTED INVARIANTS\n")
                for inv in t_norm:
                    f.write(inv + "\n")

        print(f"[TOOLS] Wrote final verified/trusted invariants to: {out_path}")
        return str(out_path)
    except Exception as e:
        print(f"[TOOLS] Error writing verified invariants: {e}")
        return f"Error: {e}"
