# cli/driver.py
import argparse
from invariants.invariant_manager import InvariantManager, InvariantSpec
from parser.solidity_parser import SolidityParser
from model.symmodel_builder import SymModelBuilder
from checker.checker import check_compiled_invariants, pretty_print_results

# === keep your existing programmatic invariants ===
def build_invariants_for_token(func_name: str, model):
    """
    Invariants for ERC20-ish tokens (SimpleToken / BadToken) and a branchy demo (tweak).
    Uses pre/post, meta.sender, and arg.* symbols produced by SymModelBuilder.
    """
    specs = []

    has_balances = "balances" in model.pre and "balances" in model.post
    has_totalsupply = "totalSupply" in model.pre and "totalSupply" in model.post

    if func_name == "transfer":
        # 1) totalSupply must be conserved by transfer
        if has_totalsupply:
            specs.append(
                InvariantSpec(
                    message="Conserve totalSupply on transfer",
                    expr={"op": "==", "args": ["post.totalSupply", "pre.totalSupply"]},
                )
            )

        if has_balances:
            # 2) Sender+Recipient sum conserved
            specs.append(
                InvariantSpec(
                    message="Sender+Recipient sum conserved",
                    expr={
                        "op": "==",
                        "args": [
                            {"op": "+", "args": [
                                {"op": "select", "args": ["post.balances", "meta.sender"]},
                                {"op": "select", "args": ["post.balances", "arg.to"]},
                            ]},
                            {"op": "+", "args": [
                                {"op": "select", "args": ["pre.balances", "meta.sender"]},
                                {"op": "select", "args": ["pre.balances", "arg.to"]},
                            ]},
                        ],
                    },
                )
            )

            # 3) Sender decreases by amount (ONLY when to != sender)
            specs.append(
                InvariantSpec(
                    message="Sender balance decreases by amount (to != sender)",
                    expr={
                        "op": "implies",
                        "args": [
                            {"op": "!=", "args": ["arg.to", "meta.sender"]},
                            {
                                "op": "==",
                                "args": [
                                    {"op": "select", "args": ["post.balances", "meta.sender"]},
                                    {"op": "-", "args": [
                                        {"op": "select", "args": ["pre.balances", "meta.sender"]},
                                        "arg.amount",
                                    ]},
                                ],
                            },
                        ],
                    },
                )
            )

            # 4) Recipient increases by amount (ONLY when to != sender)
            specs.append(
                InvariantSpec(
                    message="Recipient balance increases by amount (to != sender)",
                    expr={
                        "op": "implies",
                        "args": [
                            {"op": "!=", "args": ["arg.to", "meta.sender"]},
                            {
                                "op": "==",
                                "args": [
                                    {"op": "select", "args": ["post.balances", "arg.to"]},
                                    {"op": "+", "args": [
                                        {"op": "select", "args": ["pre.balances", "arg.to"]},
                                        "arg.amount",
                                    ]},
                                ],
                            },
                        ],
                    },
                )
            )

    elif func_name == "mint":
        if has_totalsupply:
            specs.append(
                InvariantSpec(
                    message="Mint increases totalSupply by amount",
                    expr={
                        "op": "==",
                        "args": [
                            "post.totalSupply",
                            {"op": "+", "args": ["pre.totalSupply", "arg.amount"]},
                        ],
                    },
                )
            )
        if has_balances:
            specs.append(
                InvariantSpec(
                    message="Minter balance increases by amount",
                    expr={
                        "op": "==",
                        "args": [
                            {"op": "select", "args": ["post.balances", "meta.sender"]},
                            {"op": "+", "args": [
                                {"op": "select", "args": ["pre.balances", "meta.sender"]},
                                "arg.amount",
                            ]},
                        ],
                    },
                )
            )

    elif func_name == "burn":
        if has_totalsupply:
            specs.append(
                InvariantSpec(
                    message="Burn decreases totalSupply by amount",
                    expr={
                        "op": "==",
                        "args": [
                            "post.totalSupply",
                            {"op": "-", "args": ["pre.totalSupply", "arg.amount"]},
                        ],
                    },
                )
            )
        if has_balances:
            specs.append(
                InvariantSpec(
                    message="Burner balance decreases by amount",
                    expr={
                        "op": "==",
                        "args": [
                            {"op": "select", "args": ["post.balances", "meta.sender"]},
                            {"op": "-", "args": [
                                {"op": "select", "args": ["pre.balances", "meta.sender"]},
                                "arg.amount",
                            ]},
                        ],
                    },
                )
            )

    elif func_name == "tweak":
        if has_totalsupply:
            specs.append(
                InvariantSpec(
                    message="tweak changes totalSupply by exactly x (branch-aware)",
                    expr={
                        "op": "ite",  # if-then-else
                        "args": [
                            {"op": ">", "args": ["arg.x", 10]},   # condition
                            {"op": "==", "args": [
                                "post.totalSupply",
                                {"op": "+", "args": ["pre.totalSupply", "arg.x"]}
                            ]},
                            {"op": "==", "args": [
                                "post.totalSupply",
                                {"op": "-", "args": ["pre.totalSupply", "arg.x"]}
                            ]},
                        ]
                    }
                )
            )

    # === Intentionally WRONG invariants (for counterexample demos) ===
    INCLUDE_BAD = True
    if INCLUDE_BAD:
        if func_name == "transfer":
            # Wrong: transfer should NOT increase totalSupply
            specs.append(InvariantSpec(
                message="[BAD] totalSupply increases on transfer",
                expr={"op": "==", "args": [
                    "post.totalSupply",
                    {"op": "+", "args": ["pre.totalSupply", "arg.amount"]},
                ]},
            ))
            # Wrong: sender balance should DECREASE (when to!=sender), not increase
            specs.append(InvariantSpec(
                message="[BAD] Sender balance increases by amount (to != sender)",
                expr={"op": "implies", "args": [
                    {"op": "!=", "args": ["arg.to", "meta.sender"]},
                    {"op": "==", "args": [
                        {"op": "select", "args": ["post.balances", "meta.sender"]},
                        {"op": "+", "args": [
                            {"op": "select", "args": ["pre.balances", "meta.sender"]},
                            "arg.amount",
                        ]},
                    ]},
                ]},
            ))
            # Wrong: recipient balance should INCREASE, not decrease
            specs.append(InvariantSpec(
                message="[BAD] Recipient decreases by amount (to != sender)",
                expr={"op": "implies", "args": [
                    {"op": "!=", "args": ["arg.to", "meta.sender"]},
                    {"op": "==", "args": [
                        {"op": "select", "args": ["post.balances", "arg.to"]},
                        {"op": "-", "args": [
                            {"op": "select", "args": ["pre.balances", "arg.to"]},
                            "arg.amount",
                        ]},
                    ]},
                ]},
            ))
            # Wrong: sum(sender+recipient) should be conserved, not grow by amount
            specs.append(InvariantSpec(
                message="[BAD] Sender+Recipient sum grows by amount",
                expr={"op": "==", "args": [
                    {"op": "+", "args": [
                        {"op": "select", "args": ["post.balances", "meta.sender"]},
                        {"op": "select", "args": ["post.balances", "arg.to"]},
                    ]},
                    {"op": "+", "args": [
                        {"op": "+", "args": [
                            {"op": "select", "args": ["pre.balances", "meta.sender"]},
                            {"op": "select", "args": ["pre.balances", "arg.to"]},
                        ]},
                        "arg.amount",
                    ]},
                ]},
            ))

        elif func_name == "mint":
            specs.append(InvariantSpec(
                message="[BAD] totalSupply unchanged after mint",
                expr={"op": "==", "args": ["post.totalSupply", "pre.totalSupply"]},
            ))
            specs.append(InvariantSpec(
                message="[BAD] minter balance unchanged",
                expr={"op": "==", "args": [
                    {"op": "select", "args": ["post.balances", "meta.sender"]},
                    {"op": "select", "args": ["pre.balances", "meta.sender"]},
                ]},
            ))
            specs.append(InvariantSpec(
                message="[BAD] mint decreases totalSupply by amount",
                expr={"op": "==", "args": [
                    "post.totalSupply",
                    {"op": "-", "args": ["pre.totalSupply", "arg.amount"]},
                ]},
            ))

        elif func_name == "burn":
            specs.append(InvariantSpec(
                message="[BAD] totalSupply unchanged after burn",
                expr={"op": "==", "args": ["post.totalSupply", "pre.totalSupply"]},
            ))
            specs.append(InvariantSpec(
                message="[BAD] burner balance increases by amount",
                expr={"op": "==", "args": [
                    {"op": "select", "args": ["post.balances", "meta.sender"]},
                    {"op": "+", "args": [
                        {"op": "select", "args": ["pre.balances", "meta.sender"]},
                        "arg.amount",
                    ]},
                ]},
            ))
            specs.append(InvariantSpec(
                message="[BAD] burn increases totalSupply by amount",
                expr={"op": "==", "args": [
                    "post.totalSupply",
                    {"op": "+", "args": ["pre.totalSupply", "arg.amount"]},
                ]},
            ))

        elif func_name == "tweak":
            specs.append(InvariantSpec(
                message="[BAD] tweak always adds x",
                expr={"op": "==", "args": [
                    "post.totalSupply",
                    {"op": "+", "args": ["pre.totalSupply", "arg.x"]},
                ]},
            ))
            specs.append(InvariantSpec(
                message="[BAD] tweak abs delta is x+1",
                expr={"op": "==", "args": [
                    {"op": "abs", "args": [
                        {"op": "-", "args": ["post.totalSupply", "pre.totalSupply"]}
                    ]},
                    {"op": "+", "args": ["arg.x", 1]},
                ]},
            ))

    # Fallback so the flow runs even if nothing matched
    if not specs:
        specs.append(InvariantSpec(message="Trivial true", expr={"op": "==", "args": [1, 1]}))

    return specs


def main():
    ap = argparse.ArgumentParser(
        description="InvGuard driver for ERC20-ish tokens (transfer|mint|burn|tweak), with optional LLM invariants"
    )
    ap.add_argument("sol_file", help="Path to the Solidity file (e.g., examples/SimpleToken.sol)")
    ap.add_argument("-c", "--contract", default=None, help="Contract name (optional)")
    ap.add_argument("-f", "--function", default=None, help="Function name (transfer|mint|burn|tweak)")
    ap.add_argument("--llm-invariants", default=None,
                    help="Path to plaintext/markdown invariants from InvGetter (one per line).")
    args = ap.parse_args()

    # 1) Parse → ContractIR
    cir = SolidityParser().parse(args.sol_file, contract_name=args.contract)

    # 2) Build symbolic model for the chosen function
    builder = SymModelBuilder()
    model = (builder.build_for_function_name(cir, args.function)
             if args.function else builder.build_first_function(cir))

    # 3) Choose invariants: either translate from LLM or use built-ins
    mgr = InvariantManager()

    compiled = None
    used_source = None

    if args.llm_invariants:
        try:
            from invariants.translator import translate_lines_to_specs
        except Exception as e:
            raise RuntimeError(
                "Could not import invariants.translator. "
                "Make sure invariants/translator.py is present."
            ) from e

        raw = open(args.llm_invariants, "r", encoding="utf-8").read()
        tr = translate_lines_to_specs(raw, model)

        if tr.rejected:
            print("\n[translator] Rejected lines (reason shown):")
            for line, reason in tr.rejected[:50]:
                print(f"  - {line}  =>  {reason}")
            if len(tr.rejected) > 50:
                print("  ...")

        if not tr.accepted:
            print("\n[translator] No valid invariants accepted from LLM. Falling back to built-ins.")
            specs = build_invariants_for_token(model.function_name, model)
            compiled = mgr.compile_all(specs, model)
            used_source = "built-ins"
        else:
            print(f"\n[translator] Accepted {len(tr.accepted)} invariants from LLM.")
            compiled = mgr.compile_all(tr.accepted, model)
            used_source = "LLM-translated"
    else:
        specs = build_invariants_for_token(model.function_name, model)
        compiled = mgr.compile_all(specs, model)
        used_source = "built-ins"

    # 4) Report parsing/modeling notes (useful to see what was parsed vs. skipped)
    print(f"\nFunction: {model.function_name}  (invariants: {used_source})")
    if model.notes:
        print("Notes:")
        for n in model.notes:
            print("  -", n)

    # 5) Check with the centralized checker (incremental + model slices)
    print("\n=== Invariant Checks ===")
    results = check_compiled_invariants(model, compiled)
    pretty_print_results(results)


if __name__ == "__main__":
    main()
