# checker/checker.py
# Minimal Z3 checker that consumes a SymFunctionModel and compiled invariants.

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Iterable
from z3 import Solver, Not, sat


@dataclass
class CheckOutcome:
    name: str                 # invariant name / message
    status: str               # "HOLDS", "VIOLATED", or "UNKNOWN"
    model_slice: Optional[Dict[str, Any]]  # counterexample bindings (when violated)


def _model_to_dict(m) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    try:
        for d in m.decls():
            try:
                out[d.name()] = str(m[d])
            except Exception:
                out[d.name()] = "<unprintable>"
    except Exception:
        pass
    return out


def check_one(model, inv_bool, assumptions: Optional[Iterable[Any]] = None) -> CheckOutcome:
    """
    Core check: add 'assumptions' (transition constraints), then refute invariant.
    Returns a CheckOutcome (status + optional counterexample).
    """
    s = Solver()
    for a in (assumptions or []):
        s.add(a)
    s.add(Not(inv_bool))

    r = s.check()
    if r == sat:
        m = s.model()
        return CheckOutcome(name="", status="VIOLATED", model_slice=_model_to_dict(m))
    elif str(r) == "unsat":
        return CheckOutcome(name="", status="HOLDS", model_slice=None)
    else:
        return CheckOutcome(name="", status="UNKNOWN", model_slice=None)


def check_compiled_invariants(model, compiled_invariants) -> List[CheckOutcome]:
    """
    Batch-check a list of CompiledInvariant objects (from InvariantManager.compile_all).
    """
    results: List[CheckOutcome] = []
    for inv in compiled_invariants:
        outcome = check_one(model, inv.z3_bool, model.assumptions)
        outcome.name = inv.name
        results.append(outcome)
    return results


def pretty_print_results(results: List[CheckOutcome]) -> None:
    """
    Simple terminal output helper.
    """
    print("\n=== Invariant Results ===")
    for r in results:
        tag = "✅ HOLDS" if r.status == "HOLDS" else "❌ VIOLATED" if r.status == "VIOLATED" else "❓ UNKNOWN"
        print(f"- {r.name}: {tag}")
        if r.model_slice and r.status == "VIOLATED":
            print("  Counterexample:")
            shown = 0
            for k, v in r.model_slice.items():
                print(f"    {k} = {v}")
                shown += 1
                if shown >= 30:  # avoid spamming huge models
                    print("    ...")
                    break

