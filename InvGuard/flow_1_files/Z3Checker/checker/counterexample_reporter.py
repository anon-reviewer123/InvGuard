# checker/counterexample_reporter.py

from z3 import ModelRef

def report_counterexample(model: ModelRef, limit: int = 10) -> str:
    """
    Format a Z3 counterexample model into a readable string.
    
    Args:
        model: z3.ModelRef returned by solver.model()
        limit: maximum number of bindings to print
    
    Returns:
        str formatted report
    """
    if not isinstance(model, ModelRef):
        return "<no counterexample>"

    lines = ["Counterexample found:"]
    decls = model.decls()

    for i, d in enumerate(decls):
        if i >= limit:
            lines.append(f"... and {len(decls) - limit} more bindings")
            break
        val = model[d]
        lines.append(f"  {d.name()} = {val}")

    return "\n".join(lines)


def print_counterexample(model: ModelRef, limit: int = 10):
    """
    Print the counterexample directly to stdout.
    """
    print(report_counterexample(model, limit))

