import re
from contract_parser import extract_variables
from invariant_normalizer import normalize_expression

def insert_guard_if_needed(expr: str, guards: dict, func_guards: dict) -> str:
    """
    Adds control-flow context (if-guards and modifier guards) to invariants.
    Includes:
      - Derived control-flow guards (paused == false)
      - Modifier-based guards (e.g., msg_sender == owner)
    """
    # Step 1: Insert guard for msg.value
    uses_msg_value = "msg_value" in expr
    has_guard = "msg_sender == owner" in expr or "Implies" in expr

    if uses_msg_value and not has_guard:
        print("ℹ️  Inserting generic guard: 'msg_sender == owner' for msg_value usage.")
        expr = f"Implies(msg_sender == owner, {expr})"

    # Step 2: Insert control-flow guards based on known write conditions
    for guarded_var, cond in guards.items():
        if guarded_var in expr and cond not in expr:
            print(f"ℹ️  Inserting derived guard: '{cond}' for usage of '{guarded_var}'")
            expr = f"Implies({normalize_expression(cond)}, {expr})"

    # Step 3: Insert modifier-derived guards (e.g., from onlyOwner)
    if "msg_sender" in expr:
        for fn, mod_conds in func_guards.items():
            for cond in mod_conds:
                normalized = normalize_expression(cond)
                if normalized and normalized not in expr:
                    print(f"ℹ️  Inserting function-level modifier guard: '{normalized}'")
                    expr = f"Implies({normalized}, {expr})"
                    break  # Apply only one modifier per expression

    return expr


def generate_invariants(contract_path, raw_expr_list):
    """
    Generates Z3-compatible invariants from high-level Solidity-style invariants.

    Steps:
      1. Extracts variable types, control-flow guards, and function modifier guards.
      2. Normalizes each invariant expression (msg.sender → msg_sender, etc.)
      3. Optionally wraps expressions with Implies(guard, expr).
      4. Extracts relevant variable names and types.
      5. Returns list of normalized, guarded invariants.
    """
    var_types, guard_map, func_guards = extract_variables(contract_path)
    invariant_entries = []

    for expr in raw_expr_list:
        norm_expr = normalize_expression(expr)

        if not norm_expr:
            print(f"⚠️  Invariant skipped due to normalization error.")
            invariant_entries.append({
                "expr": expr,
                "vars": {},
                "trusted": True
            })
            continue

        # Step 2–3: Insert control-flow + modifier-based guards
        guarded_expr = insert_guard_if_needed(norm_expr, guard_map, func_guards)

        # Step 4: Extract all tokens and infer types
        tokens = set(re.findall(r'\b\w+\b', guarded_expr))
        vars_in_expr = {}

        for token in tokens:
            if token in var_types:
                vars_in_expr[token] = var_types[token]
            elif token.isupper():
                vars_in_expr[token] = "const:100000"
            elif token.lower() in ["true", "false"]:
                continue
            elif token.isdigit():
                continue
            elif token == "msg_sender":
                vars_in_expr["msg_sender"] = "address"
            elif token == "msg_value":
                vars_in_expr["msg_value"] = "uint"
            else:
                pass  # skip unresolved

        invariant_entries.append({
            "expr": guarded_expr,
            "vars": vars_in_expr,
            "trusted": False
        })

    return invariant_entries

