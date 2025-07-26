import os
from solidity_parser import parser

def extract_variables(sol_file_path):
    """
    Parses the Solidity file and extracts top-level state variable declarations.
    Maps Solidity types to abstract types usable in Z3Checker:
      - uint*, int* → "int"
      - bool → "bool"
      - address → "address"
    Returns:
        dict { var_name: z3_type }
    """
    if not os.path.isfile(sol_file_path):
        raise FileNotFoundError(f"File not found: {sol_file_path}")

    try:
        ast = parser.parse_file(sol_file_path)
    except Exception as e:
        raise RuntimeError(f"Failed to parse Solidity file: {e}")

    state_vars = {}

    def map_type(sol_type):
        if sol_type.startswith("uint") or sol_type.startswith("int"):
            return "uint" if sol_type.startswith("uint") else "int"
        elif sol_type == "bool":
            return "bool"
        elif sol_type == "address":
            return "address"
        else:
            return None 

    def traverse(node):
        if isinstance(node, dict):
            if node.get("type") == "StateVariableDeclaration":
                for decl in node.get("variables", []):
                    var_name = decl.get("name")
                    type_node = decl.get("typeName", {})
                    sol_type = type_node.get("name", "") or type_node.get("typeDescriptions", {}).get("typeString", "")
                    sol_type = sol_type.split(" ")[0]  
                    z3_type = map_type(sol_type)
                    if z3_type:
                        state_vars[var_name] = z3_type
            for key in node:
                traverse(node[key])
        elif isinstance(node, list):
            for item in node:
                traverse(item)

    traverse(ast)
    return state_vars

if __name__ == "__main__":
    path = "contracts/sample.sol"
    try:
        vars_found = extract_variables(path)
        print("Extracted Variables:")
        for var, vtype in vars_found.items():
            print(f"  {var}: {vtype}")
    except Exception as e:
        print(f"Error: {e}")
