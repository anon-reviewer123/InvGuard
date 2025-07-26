import re
from contract_parser import extract_variables

def generate_invariants(contract_path, raw_expr_list):
    """
    Auto-generates invariant entries by:
    1. Extracting variable types from the Solidity contract.
    2. Scanning each invariant expression to detect variables.
    3. Assigning types to variables (or treating as consts if unknown).
    
    Args:
        contract_path (str): Path to Solidity file.
        raw_expr_list (list of str): List of invariant expressions.

    Returns:
        list of dicts: Each dict has "expr" and "vars" keys.
    """
    var_types = extract_variables(contract_path)
    invariant_entries = []

    for expr in raw_expr_list:
        tokens = set(re.findall(r'\b\w+\b', expr))  
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
            else:
                
                pass

        invariant_entries.append({
            "expr": expr,
            "vars": vars_in_expr
        })

    return invariant_entries

