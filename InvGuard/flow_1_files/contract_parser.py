import os
from solidity_parser import parser

def extract_variables(sol_file_path):
    """
    Parses the Solidity file and extracts:
    - Top-level state variable declarations
    - Control-flow guards (e.g., if-paused)
    - Modifier-based guards (e.g., onlyOwner)
    
    Returns:
        (state_vars, path_predicates, modifier_guards)
    """
    if not os.path.isfile(sol_file_path):
        raise FileNotFoundError(f"File not found: {sol_file_path}")

    try:
        ast = parser.parse_file(sol_file_path)
    except Exception as e:
        raise RuntimeError(f"Failed to parse Solidity file: {e}")

    state_vars = {}
    struct_defs = {}
    path_predicates = {}
    modifier_defs = {}      # modifier_name → condition string
    function_guards = {}    # function_name → list of guard strings

    def map_type(sol_type):
        """Normalize Solidity types to Z3 types."""
        sol_type = sol_type.strip().lower()
        if sol_type in ["uint", "uint256"]:
            return "uint"
        elif sol_type in ["int", "int256"]:
            return "int"
        elif sol_type == "bool":
            return "bool"
        elif sol_type == "address":
            return "address"
        else:
            return None

    def stringify_expression(expr):
        if not isinstance(expr, dict):
            return str(expr)
        if expr["type"] == "Identifier":
            return expr["name"]
        if expr["type"] == "IndexAccess":
            base = stringify_expression(expr["base"])
            index = stringify_expression(expr["index"])
            return f"{base}[{index}]"
        if expr["type"] == "MemberAccess":
            return f"{stringify_expression(expr['expression'])}.{expr['memberName']}"
        return "UNKNOWN_EXPR"

    def stringify_condition(cond):
        if cond is None or not isinstance(cond, dict):
            return "UNKNOWN_CONDITION"
        if cond["type"] == "BinaryOperation":
            left = stringify_expression(cond["left"])
            right = stringify_expression(cond["right"])
            op = cond["operator"]
            return f"{left} {op} {right}"
        return "UNKNOWN_CONDITION"

    def extract_struct_definitions(node):
        if isinstance(node, dict) and node.get("type") == "StructDefinition":
            struct_name = node.get("name")
            members = {}
            for member in node.get("members", []):
                member_name = member.get("name")
                type_node = member.get("typeName", {})
                sol_type = type_node.get("name", "") or type_node.get("typeDescriptions", {}).get("typeString", "")
                sol_type = sol_type.split(" ")[0]
                z3_type = map_type(sol_type)
                if z3_type:
                    members[member_name] = z3_type
            struct_defs[struct_name] = members

        elif isinstance(node, dict):
            for val in node.values():
                extract_struct_definitions(val)
        elif isinstance(node, list):
            for item in node:
                extract_struct_definitions(item)

    def capture_assignments(body, condition):
        if isinstance(body, dict):
            if body.get("type") == "ExpressionStatement":
                expr = body.get("expression", {})
                if expr.get("type") == "Assignment":
                    lhs = expr.get("left")
                    target = stringify_expression(lhs)
                    path_predicates[target] = condition
            else:
                for v in body.values():
                    capture_assignments(v, condition)
        elif isinstance(body, list):
            for item in body:
                capture_assignments(item, condition)

    def process_state_vars_and_guards(node):
        if isinstance(node, dict):
            ntype = node.get("type")

            if ntype == "StateVariableDeclaration":
                for decl in node.get("variables", []):
                    var_name = decl.get("name")
                    type_node = decl.get("typeName", {})
                    type_type = type_node.get("type")

                    if type_type == "ElementaryTypeName":
                        sol_type = type_node.get("name", "") or type_node.get("typeDescriptions", {}).get("typeString", "")
                        sol_type = sol_type.split(" ")[0]
                        z3_type = map_type(sol_type)
                        if z3_type:
                            state_vars[var_name] = z3_type

                    elif type_type == "ArrayTypeName":
                        base_type_node = type_node.get("baseTypeName", {})
                        base_type = base_type_node.get("name", "") or base_type_node.get("typeDescriptions", {}).get("typeString", "")
                        base_type = base_type.split(" ")[0]
                        base_type = map_type(base_type)
                        if base_type:
                            state_vars[var_name] = f"array<{base_type}>"
                            state_vars[f"{var_name}_length"] = "uint"

                    elif type_type == "Mapping":
                        key_type = type_node.get("keyType", {}).get("name", "") or ""
                        val_type_node = type_node.get("valueType", {})
                        val_type = val_type_node.get("name", "") or val_type_node.get("typeDescriptions", {}).get("typeString", "")
                        val_type = val_type.split(" ")[0]

                        if val_type_node.get("type") == "UserDefinedTypeName":
                            val_type = val_type_node.get("namePath", "")
                            if val_type in struct_defs:
                                for field_name, field_type in struct_defs[val_type].items():
                                    flat_name = f"{var_name}_{field_name}"
                                    state_vars[flat_name] = f"mapping({key_type}=>{field_type})"
                        else:
                            z3_val_type = map_type(val_type)
                            if key_type and z3_val_type:
                                state_vars[var_name] = f"mapping({key_type}=>{z3_val_type})"

            elif ntype == "IfStatement":
                condition = stringify_condition(node.get("condition"))
                capture_assignments(node.get("trueBody"), condition)

            elif ntype == "ModifierDefinition":
                mod_name = node.get("name")
                for stmt in node.get("body", {}).get("statements", []):
                    if stmt.get("type") == "ExpressionStatement":
                        expr = stmt.get("expression", {})
                        if expr.get("type") == "FunctionCall" and expr.get("expression", {}).get("name") == "require":
                            arg = expr.get("arguments", [])[0]
                            guard = stringify_condition(arg)
                            modifier_defs[mod_name] = guard

            elif ntype == "FunctionDefinition":
                fname = node.get("name")
                function_guards[fname] = []
                for mod in node.get("modifiers", []):
                    mod_name = mod.get("modifierName", {}).get("name")
                    if mod_name in modifier_defs:
                        function_guards[fname].append(modifier_defs[mod_name])

            for key in node:
                process_state_vars_and_guards(node[key])

        elif isinstance(node, list):
            for item in node:
                process_state_vars_and_guards(item)

    extract_struct_definitions(ast)
    process_state_vars_and_guards(ast)

    return state_vars, path_predicates, function_guards

# Optional test
if __name__ == "__main__":
    path = "contracts/sample.sol"
    try:
        vars_found, guards, mod_guards = extract_variables(path)
        print("Extracted Variables:")
        for var, vtype in vars_found.items():
            print(f"  {var}: {vtype}")
        print("\nGuarded Assignments:")
        for var, cond in guards.items():
            print(f"  {var} ← under: {cond}")
        print("\nFunction Modifier Guards:")
        for fn, guards in mod_guards.items():
            for g in guards:
                print(f"  {fn} ← guarded by: {g}")
    except Exception as e:
        print(f"❌ Error: {e}")

