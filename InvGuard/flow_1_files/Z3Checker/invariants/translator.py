# invariants/translator.py
# Turn LLM "normal" invariants (one per line) into InvariantSpec(expr=...) objects.

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional
import re

from .invariant_manager import InvariantSpec

# --- light normalization helpers ---

_ARG_ALIAS = {
    "_to": "arg.to",
    "_from": "arg.from",
    "_spender": "arg.spender",
    "_owner": "arg.owner",
    "_value": "arg.value",
    "_amount": "arg.amount",
}

_FIELD_ALIAS = {
    "this.balanceOf": "post.balances",   # function-ish to mapping name
    "this.allowance": "post.allowance",
    "this.totalSupply": "post.totalSupply",
    "this.decimals": "post.decimals",
}

def _normalize_tokens(s: str) -> str:
    t = s.strip()

    # orig(this.x) -> pre.x ; orig(x) -> pre.x   (simple fields only)
    t = re.sub(r"orig\s*\(\s*this\.([A-Za-z_]\w*)\s*\)", r"pre.\1", t)
    t = re.sub(r"orig\s*\(\s*([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)\s*\)", r"pre.\1", t)

    # this.x -> post.x (leave mapping indexing to the selector pass)
    t = re.sub(r"\bthis\.([A-Za-z_]\w*)\b", r"post.\1", t)

    # msg.sender -> meta.sender
    t = re.sub(r"\bmsg\.sender\b", "meta.sender", t)

    # argument aliases
    for k, v in _ARG_ALIAS.items():
        t = re.sub(rf"\b{k}\b", v, t)

    # .getSubValue() noise
    t = re.sub(r"\)\.getSubValue\(\)", ")", t)

    # pair spacing normalize
    t = re.sub(r"\bpair\s*\(\s*", "pair(", t)
    t = re.sub(r"\s*,\s*", ",", t)

    # balanceOf / allowance aliases after "this." pass
    for k, v in _FIELD_ALIAS.items():
        t = t.replace(k, v)

    return t

# Turn mapping indexing A[B] into select(A,B) (supports nesting)
_IDX_PAT = re.compile(r"([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)\s*\[\s*([^\[\]]+?)\s*\]")

def _brackets_to_select(expr: str) -> str:
    prev, out = None, expr
    while prev != out:
        prev = out
        out = _IDX_PAT.sub(lambda m: f"select({m.group(1)},{m.group(2)})", out)
    return out

def _parens_balanced(s: str) -> bool:
    d = 0
    for ch in s:
        if ch == '(': d += 1
        elif ch == ')': d -= 1
        if d < 0: return False
    return d == 0

def _split_top(s: str, sep: str) -> Optional[int]:
    d1 = d2 = 0  # () and []
    i = 0
    L, LS = len(s), len(sep)
    while i <= L - LS:
        ch = s[i]
        if ch == '(': d1 += 1
        elif ch == ')': d1 -= 1
        elif ch == '[': d2 += 1
        elif ch == ']': d2 -= 1
        if d1 == 0 and d2 == 0 and s[i:i+LS] == sep:
            return i
        i += 1
    return None

def _split_top_args_inside_parens(s: str) -> List[str]:
    """Split 'a,b,c' respecting nested () and []."""
    args: List[str] = []
    d1 = d2 = 0
    buf: List[str] = []
    for ch in s:
        if ch == '(': d1 += 1
        elif ch == ')': d1 -= 1
        elif ch == '[': d2 += 1
        elif ch == ']': d2 -= 1
        if ch == ',' and d1 == 0 and d2 == 0:
            args.append(''.join(buf).strip()); buf = []
        else:
            buf.append(ch)
    if buf:
        args.append(''.join(buf).strip())
    return args

# --- NEW: rewrite orig(select(A,B)) -> select(pre.<A>, B) ---
def _rewrite_orig_over_select(s: str) -> str:
    out = []
    i = 0
    while i < len(s):
        j = s.find("orig(", i)
        if j == -1:
            out.append(s[i:])
            break
        # copy up to j
        out.append(s[i:j])
        # find matching ')'
        k = j + 5  # after 'orig('
        depth = 1
        while k < len(s) and depth > 0:
            if s[k] == '(':
                depth += 1
            elif s[k] == ')':
                depth -= 1
            k += 1
        if depth != 0:
            # unbalanced; just append rest
            out.append(s[j:])
            break
        inner = s[j+5:k-1].strip()
        # If inner is select(...), rewrite first arg's post.->pre.
        if inner.startswith("select(") and _parens_balanced(inner):
            inside = inner[len("select("):-1].strip() if inner.endswith(")") else inner[7:]
            parts = _split_top_args_inside_parens(inside)
            if len(parts) == 2:
                a0 = parts[0].strip()
                a1 = parts[1].strip()
                # flip post. -> pre. in the first arg only
                a0 = re.sub(r"\bpost\.", "pre.", a0)
                out.append(f"select({a0},{a1})")
            else:
                out.append(inner)  # fallback: keep as-is
        else:
            # Generic case: flip leading post. -> pre. (e.g., orig(post.x))
            inner2 = re.sub(r"\bpost\.", "pre.", inner)
            out.append(inner2)
        i = k
    return ''.join(out)

# --- minimal infix -> AST for your encoder schema ---

def _parse_arith(x: str) -> Any:
    x = x.strip()
    if x.startswith("(") and x.endswith(")") and _parens_balanced(x):
        return parse_infix(x[1:-1].strip())
    # + / - at top level (left-assoc)
    for tok in ["+", "-"]:
        i = _split_top(x, tok)
        if i is not None:
            L, R = x[:i].strip(), x[i+1:].strip()
            return {"op": tok, "args": [_parse_arith(L), _parse_term(R)]}
    return _parse_term(x)

def _parse_term(x: str) -> Any:
    x = x.strip()
    i = _split_top(x, "*")
    if i is not None:
        L, R = x[:i].strip(), x[i+1:].strip()
        return {"op": "*", "args": [_parse_term(L), _parse_atom(R)]}
    return _parse_atom(x)

def _parse_atom(tok: str) -> Any:
    t = tok.strip()

    # function-style atoms -> AST nodes
    if t.startswith("select(") and t.endswith(")") and _parens_balanced(t):
        inside = t[len("select("):-1].strip()
        parts = _split_top_args_inside_parens(inside)
        if len(parts) != 2:
            raise ValueError("select expects 2 args")
        return {"op": "select", "args": [parse_infix(parts[0]), parse_infix(parts[1])]}

    # (Optional future) pair(a,b) as single-string key for 2D maps.
    # if t.startswith("pair(") and t.endswith(")") and _parens_balanced(t):
    #     inside = t[len("pair("):-1].strip()
    #     parts = _split_top_args_inside_parens(inside)
    #     if len(parts) != 2:
    #         raise ValueError("pair expects 2 args")
    #     return f"pair({parts[0]},{parts[1]})"

    # already-normalized names / literals → keep as string
    return t

def parse_infix(line: str) -> Dict[str, Any]:
    s = line.strip()

    # implication
    for sym in ["->", "=>"]:
        i = _split_top(s, sym)
        if i is not None:
            L, R = s[:i].strip(), s[i+len(sym):].strip()
            return {"op":"implies", "args":[parse_infix(L), parse_infix(R)]}

    # if-then-else
    m = re.match(r'^\s*if\s+(.+?)\s+then\s+(.+?)(?:\s+else\s+(.+))?$', s, flags=re.IGNORECASE)
    if m:
        c, t, e = m.group(1).strip(), m.group(2).strip(), (m.group(3) or "").strip()
        if e:
            return {"op":"ite", "args":[parse_infix(c), parse_infix(t), parse_infix(e)]}
        return {"op":"implies", "args":[parse_infix(c), parse_infix(t)]}

    # boolean or/and
    for sym, op in [("||","or"), (" or ","or"), ("&&","and"), (" and ","and")]:
        i = _split_top(s, sym)
        if i is not None:
            L, R = s[:i].strip(), s[i+len(sym):].strip()
            return {"op": op, "args":[parse_infix(L), parse_infix(R)]}

    # comparisons
    for sym in ["==","!=",">=","<=",">","<"]:
        i = _split_top(s, sym)
        if i is not None:
            L, R = s[:i].strip(), s[i+len(sym):].strip()
            return {"op": sym, "args":[_parse_arith(L), _parse_arith(R)]}

    # arithmetic-only
    return _parse_arith(s)

# --- public API ---

@dataclass
class TranslationResult:
    accepted: List[InvariantSpec]
    rejected: List[Tuple[str, str]]  # (line, reason)

def translate_lines_to_specs(raw_text: str, model) -> TranslationResult:
    """
    raw_text: LLM output, one invariant per line (bullets ok).
    Returns InvariantSpec(expr=...) list ready for InvariantManager.compile_all.
    """
    accepted: List[InvariantSpec] = []
    rejected: List[Tuple[str, str]] = []

    # strip code fences / bullets
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_+-]*\s*|\s*```$", "", text, flags=re.MULTILINE).strip()

    lines = []
    for ln in text.splitlines():
        s = re.sub(r'^\s*(?:[-*•]|\d+[.)])\s*', "", ln).strip()
        if not s:
            continue
        # skip headers like Foo.bar(...):::EXIT1
        if ":::" in s:
            continue
        lines.append(s)

    for i, line in enumerate(lines, 1):
        try:
            norm = _normalize_tokens(line)
            norm = _brackets_to_select(norm)
            norm = _rewrite_orig_over_select(norm)  # <<-- NEW

            # Skip non-compilable whole-state frames
            if norm == "post == pre":
                rejected.append((line, "whole-contract frame not supported"))
                continue

            ast = parse_infix(norm)

            # VERY small schema check: known ops and arity
            def _check(node):
                if isinstance(node, dict):
                    op = node.get("op"); args = node.get("args", [])
                    if op not in {"and","or","not","implies","=>","==","!=",">=","<=",">","<","+","-","*","select","ite"}:
                        raise ValueError(f"unsupported op {op}")
                    if op == "not" and len(args) != 1:
                        raise ValueError("not arity")
                    if op in {"implies","=>","==","!=",">=","<=",">","<","+","-","*"} and len(args) != 2:
                        raise ValueError(f"{op} arity")
                    if op == "ite" and len(args) != 3:
                        raise ValueError("ite arity")
                    for a in args:
                        _check(a)

            _check(ast)
            accepted.append(InvariantSpec(message=f"inv_{i}", expr=ast))
        except Exception as e:
            rejected.append((line, str(e)))

    return TranslationResult(accepted=accepted, rejected=rejected)
