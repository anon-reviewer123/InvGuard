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
        Convert variable type strings to Z3 variables.
        Supported types:
          - int → Z3 Int
          - uint → Z3 Int + constraint (var >= 0)
          - bool → Z3 Bool
          - address → Z3 Int
          - const:<value> → Z3 IntVal(value)
        """
        context = {}

        for var_name, var_type in var_declarations.items():
            if var_type == "int":
                var = Int(var_name)
                context[var_name] = var
            elif var_type == "uint":
                var = Int(var_name)
                context[var_name] = var
                self.extra_constraints.append(var >= 0)
            elif var_type == "bool":
                context[var_name] = Bool(var_name)
            elif var_type == "address":
                context[var_name] = Int(var_name)  # treating address as Int
            elif var_type.startswith("const:"):
                val = int(var_type.split(":")[1])
                context[var_name] = IntVal(val)
            else:
                raise ValueError(f"Unsupported variable type: {var_type}")

        return context

    def is_always_true(self, invariant_expr: str, variable_definitions: dict):
        """
        Checks whether the invariant is always true for all possible variable assignments.
        Uses: NOT(expr), and checks if that is UNSAT (i.e., no counterexample exists).
        Returns: (True, None) if always holds, or (False, counterexample model)
        """
        self.reset_solver()

        # Step 1: Declare variables
        try:
            context = self.define_variables(variable_definitions)
        except ValueError as e:
            raise RuntimeError(f"Variable parsing error: {e}")

        # Step 2: Parse expression
        try:
            expr = eval(invariant_expr, {}, context)
        except Exception as e:
            raise RuntimeError(f"Error parsing invariant expression: {e}")

        # Step 3: Add the negation of the invariant
        self.solver.add(Not(expr))

        # Step 4: Add extra constraints (e.g., uint >= 0)
        for constraint in self.extra_constraints:
            self.solver.add(constraint)

        # Step 5: Solve
        result = self.solver.check()

        if result == unsat:
            return True, None  # ✅ Invariant always holds
        elif result == sat:
            return False, self.solver.model()  # ❌ Found counterexample
        else:
            raise RuntimeError("Z3 returned 'unknown'. Could not determine result.")
