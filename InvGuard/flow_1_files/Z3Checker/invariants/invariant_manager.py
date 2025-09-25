# invariants/invariant_manager.py
# Manage invariant specs (templates or expressions) and compile them to Z3 for a given SymFunctionModel.

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
import json
import os
import re

try:
    import yaml  # optional; only used if available for .yml/.yaml
    _HAS_YAML = True
except Exception:
    _HAS_YAML = False

try:
    from z3 import (
        BoolVal, IntVal, BitVecVal, Bool, BitVec, Array, Select, Store,
        And, Or, Not, Implies, If, UGE, ULE, UGT, ULT, is_bool, is_bv
    )
except Exception as e:
    raise RuntimeError("Install z3-solver: pip install z3-solver")

BV256_BITS = 256
BV160_BITS = 160


# ---------------------------
# Public types
# ---------------------------

@dataclass
class InvariantSpec:
    """High-level invariant spec before compilation."""
    template: Optional[str] = None       # e.g., 'R1','O3','A1','EC1','EC2','D3'
    params: Dict[str, Any] = None        # template params
    expr: Optional[Dict[str, Any]] = None  # generic expression tree
    message: Optional[str] = None
    on_success_only: bool = True

@dataclass
class CompiledInvariant:
    """Compiled invariant ready for the solver."""
    name: str
    z3_bool: Any           # z3 BoolRef
    raw: InvariantSpec     # original spec


# ---------------------------
# Invariant Manager
# ---------------------------

class InvariantManager:
    """
    Compiles invariant specs (template or expr) against a SymFunctionModel produced by SymModelBuilder.
    Variable references allowed in expr trees:
      - 'pre.X' / 'post.X' / 'meta.Y' / 'arg.Z'
      - Arrays (mappings): use op 'select' with args ['pre.balances','arg.sender'] etc.
      - Also supports 'msg.sender' and 'msg.value' as aliases for 'meta.sender'/'meta.value'.
    Supported ops: and, or, not, implies (=>), ==, !=, >=, <=, >, <, +, -, *,
                   select (for mappings), abs.
    """

    def __init__(self, address_bits: int = BV160_BITS, uint_bits: int = BV256_BITS) -> None:
        self.addr_bits = address_bits
        self.uint_bits = uint_bits
        self._hex_addr_re = re.compile(r"^0x[0-9a-fA-F]{1,40}$")

    # ---------- Loading ----------

    def load_specs(self, src: Union[str, List[Dict[str, Any]]]) -> List[InvariantSpec]:
        items: List[Dict[str, Any]]
        if isinstance(src, list):
            items = src
        elif isinstance(src, str):
            path = src
            if not os.path.exists(path):
                raise FileNotFoundError(path)
            if path.endswith(".json"):
                items = json.load(open(path, "r", encoding="utf-8"))
            elif path.endswith((".yml", ".yaml")):
                if not _HAS_YAML:
                    raise RuntimeError("pyyaml not installed. pip install pyyaml")
                items = yaml.safe_load(open(path, "r", encoding="utf-8"))
            else:
                raise ValueError("Unsupported file type. Use .json or .yml/.yaml")
        else:
            raise TypeError("src must be a path or a list of dicts")

        specs: List[InvariantSpec] = []
        for it in items:
            specs.append(
                InvariantSpec(
                    template=it.get("template"),
                    params=it.get("params") or {},
                    expr=it.get("expr"),
                    message=it.get("message"),
                )
            )
        return specs

    # ---------- Compilation ----------

    def compile_all(self, specs: List[InvariantSpec], model) -> List[CompiledInvariant]:
        out: List[CompiledInvariant] = []
        for i, sp in enumerate(specs):
            z = self._compile_one(sp, model)
            name = sp.message or sp.template or f"invariant_{i}"
            out.append(CompiledInvariant(name=name, z3_bool=z, raw=sp))
        return out

    def _compile_one(self, sp: InvariantSpec, model) -> Any:
        if sp.template:
            z = self._encode_template(sp.template, sp.params or {}, model)
        elif sp.expr:
            z = self._encode_expr(sp.expr, model)
        else:
            raise ValueError("InvariantSpec must have either 'template' or 'expr'.")

        if getattr(sp, "on_success_only", True):
            try:
                from z3 import Implies, Not
                revert = model.meta.get("revert_taken")
                if revert is not None:
                    z = Implies(Not(revert), z)
            except Exception:
                pass
        return z

    # ---------- Expression encoding ----------

    def _encode_expr(self, node: Any, model) -> Any:
        if isinstance(node, bool):
            return BoolVal(node)
        if isinstance(node, int):
            return BitVecVal(node & ((1 << self.uint_bits) - 1), self.uint_bits)
        if isinstance(node, str):
            sym = self._resolve_name(node, model)
            if sym is not None:
                return sym
            lit = self._try_literal(node)
            if lit is not None:
                return lit
            raise KeyError(f"Unknown symbol '{node}'")

        if not isinstance(node, dict) or "op" not in node:
            raise ValueError(f"Bad expr node: {node!r}")

        op = node["op"].lower()
        args = node.get("args", [])

        def E(x):
            return self._encode_expr(x, model)

        def _cmp_ge(a, b): return UGE(a, b) if is_bv(a) or is_bv(b) else (a >= b)
        def _cmp_le(a, b): return ULE(a, b) if is_bv(a) or is_bv(b) else (a <= b)
        def _cmp_gt(a, b): return UGT(a, b) if is_bv(a) or is_bv(b) else (a > b)
        def _cmp_lt(a, b): return ULT(a, b) if is_bv(a) or is_bv(b) else (a < b)

        if op == "and":      return And(*[E(a) for a in args])
        if op == "or":       return Or(*[E(a) for a in args])
        if op == "not":
            if len(args) != 1: raise ValueError("not expects 1 arg")
            return Not(E(args[0]))
        if op in ("=>", "implies"):
            if len(args) != 2: raise ValueError("implies expects 2 args")
            return Implies(E(args[0]), E(args[1]))
        if op == "==":  a, b = args; return E(a) == E(b)
        if op == "!=":  a, b = args; return E(a) != E(b)
        if op == ">=":  a, b = E(args[0]), E(args[1]); return _cmp_ge(a, b)
        if op == "<=":  a, b = E(args[0]), E(args[1]); return _cmp_le(a, b)
        if op == ">":   a, b = E(args[0]), E(args[1]); return _cmp_gt(a, b)
        if op == "<":   a, b = E(args[0]), E(args[1]); return _cmp_lt(a, b)
        if op == "+":   a, b = args; return E(a) + E(b)
        if op == "-":   a, b = args; return E(a) - E(b)
        if op == "*":   a, b = args; return E(a) * E(b)
        if op == "abs":
            if len(args) != 1: raise ValueError("abs expects 1 arg")
            x = E(args[0]); zero = BitVecVal(0, self.uint_bits)
            if is_bool(x):
                x = If(x, BitVecVal(1, self.uint_bits), BitVecVal(0, self.uint_bits))
            return If(_cmp_ge(x, zero), x, -x)
        if op == "select":
            if len(args) != 2: raise ValueError("select expects 2 args")
            arr = E(args[0]); key = E(args[1])
            return Select(arr, key)
        if op in ("ite", "if"):
            if len(args) != 3: raise ValueError("ite expects 3 args")
            c = E(args[0]); t = E(args[1]); e = E(args[2])
            return If(c, t, e)

        raise NotImplementedError(f"Unsupported op in expr: {op!r}")

    def _encode_template(self, tid: str, params: Dict[str, Any], model) -> Any:
        tid = tid.upper().strip()
        if tid == "R1":
            depth = self._resolve_name("meta.call_depth", model)
            limit = BitVecVal(int(params.get("limit", 1)), self.uint_bits)
            return depth <= limit
        if tid == "O3":
            xname = params["x"]
            burn_flag_name = params.get("burnFlag", "burnPath")
            x_pre = self._resolve_name(f"pre.{xname}", model)
            x_post = self._resolve_name(f"post.{xname}", model)
            burn_flag = self._resolve_name(f"meta.{burn_flag_name}", model)
            if is_bv(x_post) and is_bv(x_pre):
                lhs = UGE(x_post, x_pre)
            else:
                lhs = (x_post >= x_pre)
            lhs_bool = lhs if is_bool(lhs) else (lhs != BitVecVal(0, self.uint_bits))
            rhs_bool = burn_flag if is_bool(burn_flag) else (burn_flag != BitVecVal(0, self.uint_bits))
            return Or(lhs_bool, rhs_bool)
        if tid == "A1":
            sender = self._resolve_name("meta.sender", model)
            role_set = params.get("roleSet", [])
            if not role_set:
                raise ValueError("A1 requires non-empty params.roleSet (addresses).")
            return Or(*[sender == self._addr_to_bv(a) for a in role_set])
        if tid == "EC1":
            depth = self._resolve_name("meta.call_depth", model)
            limit = BitVecVal(int(params.get("limit", params.get("d", 1))), self.uint_bits)
            return depth <= limit
        if tid == "EC2":
            target = self._resolve_name("meta.target", model)
            wl = params.get("whitelist", [])
            if not wl:
                raise ValueError("EC2 requires non-empty params.whitelist (addresses).")
            return Or(*[target == self._addr_to_bv(a) for a in wl])
        if tid == "D3":
            return self._resolve_name("meta.all_calls_success", model)
        raise NotImplementedError(f"Template {tid!r} not implemented yet.")

    # ---------- Name / literal resolution ----------

    def _resolve_name(self, name: str, model) -> Optional[Any]:
        if not isinstance(name, str):
            return None
        s = name.strip()

        # --- Solidity builtins (aliases to meta.*) ---
        if s == "msg.sender":
            if "sender" in model.meta and model.meta["sender"] is not None:
                return model.meta["sender"]
            if "msg_sender" in model.meta and model.meta["msg_sender"] is not None:
                return model.meta["msg_sender"]
            return BitVec("meta.sender", self.addr_bits)

        if s == "msg.value":
            if "value" in model.meta and model.meta["value"] is not None:
                return model.meta["value"]
            if "msg_value" in model.meta and model.meta["msg_value"] is not None:
                return model.meta["msg_value"]
            return BitVec("meta.value", self.uint_bits)

        if s.startswith("pre."):  return model.pre.get(s[4:])
        if s.startswith("post."): return model.post.get(s[5:])
        if s.startswith("meta."): return model.meta.get(s[5:])
        if s.startswith("arg."):  return model.arg_symbols.get(s[4:])

        if s in model.arg_symbols: return model.arg_symbols[s]
        if s in model.pre: return model.pre[s]
        if s in model.post: return model.post[s]
        if s in model.meta: return model.meta[s]

        lit = self._try_literal(s)
        if lit is not None:
            return lit
        return None

    def _try_literal(self, tok: str) -> Optional[Any]:
        t = tok.strip().lower()
        if t == "true":  return BoolVal(True)
        if t == "false": return BoolVal(False)
        if t.isdigit():
            return BitVecVal(int(t), self.uint_bits)
        if self._hex_addr_re.match(tok):
            return BitVecVal(int(tok, 16), self.addr_bits)
        return None

    def _addr_to_bv(self, a: Union[str, int]) -> Any:
        if isinstance(a, int):
            return BitVecVal(a, self.addr_bits)
        if isinstance(a, str):
            s = a.strip().lower()
            if s.startswith("0x"):
                return BitVecVal(int(s, 16), self.addr_bits)
            if s.startswith("addr:"):
                return BitVecVal(int(s.split(":", 1)[1], 16), self.addr_bits)
            return BitVecVal(int(s, 16), self.addr_bits)
        raise TypeError(f"Unsupported address literal: {a!r}")
