import re

def normalize_expression(expr: str) -> str:
    """
    Normalize Solidity-style invariants into Z3-compatible Python syntax.
    Converts:
      - msg.sender → msg_sender
      - msg.value → msg_value
      - map[key].field → map_field[key]
      - => → Implies(...)
      - true/false → BoolVal(...)
      - len(arr) → arr_length
      - user → msg_sender (optional and marked)
    """
    original_expr = expr.strip()

    # Step 0: Reject expressions that contain informal or invalid syntax
    unsupported_keywords = ["->", "after", "before", "transfer("]
    if any(tok in original_expr for tok in unsupported_keywords):
        print(f"⚠️  Skipping unsupported expression: '{original_expr}'")
        return None

    # Step 1: Solidity → Python-compatible substitutions
    expr = expr.replace("msg.sender", "msg_sender")
    expr = expr.replace("msg.value", "msg_value")
    expr = expr.replace("true", "BoolVal(True)")
    expr = expr.replace("false", "BoolVal(False)")

    # Step 2: Replace a => b with Implies(a, b)
    expr = _replace_implies(expr)

    # Step 3: Replace map[key].field → map_field[key]
    expr = _flatten_struct_access(expr)

    # Step 4: Replace remaining a.b → a_b
    expr = re.sub(r'(\w+)\.(\w+)', r'\1_\2', expr)

    # Step 5: Replace len(arr) → arr_length
    expr, len_replaced = _replace_len(expr)

    # Step 6: Optionally replace `user` with msg_sender
    expr = re.sub(r'\buser\b', "msg_sender", expr)

    # Final validation
    if not expr.strip():
        print(f"⚠️  Empty or invalid after normalization: '{original_expr}'")
        return None

    if len_replaced:
        print(f"ℹ️  Replaced 'len(...)' with symbolic '..._length'.")

    return expr


def _replace_implies(expr: str) -> str:
    if "=>" not in expr:
        return expr
    try:
        parts = expr.split("=>", 1)
        lhs = parts[0].strip()
        rhs = parts[1].strip()
        return f"Implies({lhs}, {rhs})"
    except Exception as e:
        print(f"⚠️  Error parsing '=>' in expression: {expr} → {e}")
        return expr


def _flatten_struct_access(expr: str) -> str:
    """
    Converts struct accesses like map[key].field → map_field[key]
    Supports general pattern: <map>[<key>].<field> → <map>_<field>[<key>]
    """
    pattern = r'(\w+)\[([^\]]+)\]\.(\w+)'

    def replacer(match):
        map_name = match.group(1)
        key_expr = match.group(2)
        field = match.group(3)
        return f"{map_name}_{field}[{key_expr}]"

    return re.sub(pattern, replacer, expr)


def _replace_len(expr: str):
    """
    Replace all instances of len(X) with X_length
    """
    matches = re.findall(r'len\((\w+)\)', expr)
    for arr in matches:
        expr = expr.replace(f"len({arr})", f"{arr}_length")
    return expr, bool(matches)

