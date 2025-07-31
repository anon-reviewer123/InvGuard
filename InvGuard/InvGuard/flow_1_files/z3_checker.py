from z3 import *

class Z3Checker:
    def __init__(self):
        self.solver = Solver()
        self.extra_constraints = []

    def reset_solver(self):
        self.solver = Solver()
        self.extra_constraints = []

    def define_variables(self, var_declarations: dict):
        """
        Converts variable type strings to Z3 variables.
        Supports:
          - int → Z3 Int
          - uint → Z3 Int + (var >= 0)
          - bool → Z3 Bool
          - address → Z3 Int
          - const:<value> → Z3 IntVal(value)
          - mapping(address=>T) → Z3 Array(Int, Z3Type)
          - array<T> → Z3 Array(Int, Z3Type)
        Also includes:
          - Built-ins: true, false
          - Special vars: msg_sender, msg_value
        """
        context = {}

        # Built-in constants and Solidity reserved words
        context["true"] = BoolVal(True)
        context["false"] = BoolVal(False)
        context["msg_sender"] = Int("msg_sender")
        context["msg_value"] = Int("msg_value")  # ✅ NEW: symbolic representation of msg.value
        self.extra_constraints.append(context["msg_value"] >= 0)  # ✅ uint constraint

        for var_name, var_type in var_declarations.items():
            # Handle constant values (e.g., const:5)
            if var_type.startswith("const:"):
                val = int(var_type.split(":", 1)[1])
                context[var_name] = IntVal(val)

            # Basic scalar types
            elif var_type == "int":
                context[var_name] = Int(var_name)

            elif var_type == "uint":
                z3_var = Int(var_name)
                context[var_name] = z3_var
                self.extra_constraints.append(z3_var >= 0)

            elif var_type == "bool":
                context[var_name] = Bool(var_name)

            elif var_type == "address":
                context[var_name] = Int(var_name)  # treat address as Int

            # Arrays: e.g., array<uint>
            elif var_type.startswith("array<"):
                base = var_type[len("array<"):-1].strip()
                if base in ["uint", "int"]:
                    context[var_name] = Array(var_name, IntSort(), IntSort())
                elif base == "bool":
                    context[var_name] = Array(var_name, IntSort(), BoolSort())
                else:
                    raise ValueError(f"Unsupported array base type: {base}")

            # Mappings: e.g., mapping(address=>uint)
            elif var_type.startswith("mapping("):
                key_type = var_type.split("(", 1)[1].split("=>")[0].strip()
                val_type = var_type.split("=>")[1].rstrip(")").strip()

                key_sort = IntSort()  # treat all keys as Int (including address)
                if val_type in ["uint", "int"]:
                    context[var_name] = Array(var_name, key_sort, IntSort())
                elif val_type == "bool":
                    context[var_name] = Array(var_name, key_sort, BoolSort())
                else:
                    raise ValueError(f"Unsupported mapping value type: {val_type}")

            else:
                raise ValueError(f"Unsupported variable type: {var_type}")

        return context

    def is_always_true(self, invariant_expr: str, variable_definitions: dict):
        """
        Checks whether the invariant is always true using Z3.
        Returns:
            (True, None) if invariant always holds,
            (False, counterexample) if it can fail
        """
        self.reset_solver()

        # Step 1: Create variable context
        try:
            context = self.define_variables(variable_definitions)
        except ValueError as e:
            raise RuntimeError(f"Variable parsing error: {e}")

        # Step 2: Include Z3 functions for safe eval
        safe_builtins = {
            "Implies": Implies,
            "And": And,
            "Or": Or,
            "Not": Not,
            "BoolVal": BoolVal,
            "IntVal": IntVal,
            "Select": Select,
        }
        safe_builtins.update(context)

        # Step 3: Parse the expression
        try:
            expr = eval(invariant_expr, safe_builtins, {})
        except Exception as e:
            raise RuntimeError(f"Error parsing invariant expression: {e}")

        # Step 4: Add negation of the invariant
        self.solver.add(Not(expr))

        # Step 5: Add type-specific extra constraints
        for constraint in self.extra_constraints:
            self.solver.add(constraint)

        # Step 6: Solve
        result = self.solver.check()
        if result == unsat:
            return True, None
        elif result == sat:
            return False, self.solver.model()
        else:
            raise RuntimeError("Z3 returned 'unknown'. Could not determine result.")

