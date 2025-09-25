# model/symmodel_builder.py
# Build a symbolic (pre, post, meta, assumptions) model for a function
# from the Tiny-IR produced by parser/solidity_parser.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple
import re

try:
    from z3 import (
        Bool, BoolVal, And, Or, Not, If,
        BitVecSort, BitVec, BitVecVal, ArraySort, Array, Store, Select,
        UGE, ULE, UGT, ULT, simplify, is_true, is_false
    )
except Exception as e:
    raise RuntimeError("Install z3-solver: pip install z3-solver")

# Sorts we’ll use for EVM-ish modeling
BV256 = BitVecSort(256)
BV160 = BitVecSort(160)

# ---- IR type hints (kept minimal; we only inspect fields we need) ----
# VarDecl(name:str, ty:str, is_mapping:bool, key_ty:str|None, val_ty:str|None)
# FunctionIR(name:str, args:List[VarDecl], body:List[dict])
# ContractIR(name:str, state:List[VarDecl], functions:List[FunctionIR])

# ----------------------------------------------------------------------
# Public result type
# ----------------------------------------------------------------------
@dataclass
class SymFunctionModel:
    contract_name: str
    function_name: str
    pre: Dict[str, Any]
    post: Dict[str, Any]
    meta: Dict[str, Any]
    assumptions: List[Any]      # BoolRefs to conjoin in checks
    arg_symbols: Dict[str, Any] # z3 symbols for function args
    notes: List[str]            # warnings / skipped statements

# ----------------------------------------------------------------------
# Builder
# ----------------------------------------------------------------------
class SymModelBuilder:
    def __init__(self) -> None:
        pass

    # ----- entry points -----
    def build_for_function_name(self, cir, func_name: str) -> SymFunctionModel:
        """
        Build a symbolic model for the named function in the contract IR.
        Ensures parser/encoder notes get attached to the model so driver.py can print them.
        """
        f = None
        for fn in cir.functions:
            if fn.name == func_name:
                f = fn
                break
        if f is None:
            raise ValueError(f"Function '{func_name}' not found in contract {cir.name}.")

        model = self._encode_function(cir, f)
        return model

    def build_first_function(self, cir) -> SymFunctionModel:
        if not cir.functions:
            raise ValueError(f"No functions in contract {cir.name}.")
        return self._encode_function(cir, cir.functions[0])

    # ----- core encoder -----
    def _encode_function(self, cir, fn) -> SymFunctionModel:
        notes: List[str] = []

        # 1) make storage symbols (pre/post); mappings -> Arrays, scalars -> BitVec/Bool
        pre, post = self._mk_state_symbols(cir.state)

        # 2) meta/environment symbols (match checker expectations)
        meta = {
            'sender': BitVec("meta.sender", 160),
            'call_depth': BitVec("meta.call_depth", 256),
            'target': BitVec("meta.target", 160),
            'all_calls_success': Bool("meta.all_calls_success"),
            'revert_taken': Bool("meta.revert_taken"),
            'value': BitVec("meta.value", 256),  # <-- added so msg.value / meta.value is available
        }

        # 3) argument symbols
        arg_syms: Dict[str, Any] = {}
        for a in fn.args:
            if a.ty == 'uint256':
                arg_syms[a.name] = BitVec(f"arg.{a.name}", 256)
            elif a.ty == 'address':
                arg_syms[a.name] = BitVec(f"arg.{a.name}", 160)
            elif a.ty == 'bool':
                arg_syms[a.name] = Bool(f"arg.{a.name}")
            else:
                # default to 256-bit if unknown numeric
                arg_syms[a.name] = BitVec(f"arg.{a.name}", 256)

        # 4) path condition
        ok_curr = BoolVal(True)

        # working copy of storage (curr) and bind to post at the end
        curr = dict(pre)

        # 5) walk the body
        for st in fn.body:
            op = st.get('op')

            # --- Structured IR path (preferred) ---
            if op == 'require' and 'cond' in st:
                cond = self._E(st['cond'], curr, arg_syms)
                ok_curr = And(ok_curr, cond)
                continue

            if op == 'store_map' and all(k in st for k in ('var','key','val')):
                var = st['var']
                key = self._E(st['key'], curr, arg_syms)
                val = self._E(st['val'], curr, arg_syms)
                if var not in curr:
                    notes.append(f"[skip] unknown mapping var '{var}'")
                    continue
                curr[var] = If(ok_curr, Store(curr[var], key, val), curr[var])
                continue

            if op == 'store' and all(k in st for k in ('var','val')):
                var = st['var']
                val = self._E(st['val'], curr, arg_syms)
                if var not in curr:
                    notes.append(f"[skip] unknown var '{var}'")
                    continue
                curr[var] = If(ok_curr, val, curr[var])
                continue

            if op == 'external_call' and 'target' in st:
                tgt = self._E(st['target'], curr, arg_syms)
                meta['target'] = tgt
                meta['call_depth'] = meta['call_depth'] + BitVecVal(1, 256)
                continue

            # --- If/Else (structured or coarse) ---
            if op == 'if':
                # resolve cond from 'cond' or 'cond_src'
                cond = None
                if 'cond' in st:
                    cond = self._E(st['cond'], curr, arg_syms)
                elif 'cond_src' in st:
                    # try require-style first, then generic expr (e.g., "x > 10")
                    cond = self._parse_cond_src(st['cond_src'], curr, arg_syms, notes)
                    if cond is None:
                        cond = self._parse_expr_src(st['cond_src'], curr, arg_syms, notes)

                if cond is None:
                    notes.append(f"[skip] unparsed if cond: {st.get('cond_src')}")
                    continue

                then_state, _ = self._encode_block(st.get('then', []), dict(curr), ok_curr, arg_syms, notes)
                else_state, _ = self._encode_block(st.get('else', []), dict(curr), ok_curr, arg_syms, notes)

                # merge branches
                curr = self._merge_states(cond, then_state, else_state)
                continue

            # --- Coarse Slither string path (fallback) ---
            if op == 'require' and 'cond_src' in st:
                txt = st['cond_src'].strip()
                if ")(" in txt:
                    txt = txt.split(")(", 1)[1].strip()
                if "," in txt:
                    txt = txt.rsplit(",", 1)[0].strip()
                txt = txt.replace("msg.sender", "msg_sender")

                cond = self._parse_cond_src(txt, curr, arg_syms, notes)
                if cond is not None:
                    ok_curr = And(ok_curr, cond)
                else:
                    notes.append(f"[skip] unparsed require: {st['cond_src']}")
                continue

            if op == 'store_map' and 'key_src' in st and 'val_src' in st and 'var' in st:
                var = st['var']
                key_expr = self._parse_expr_src(st['key_src'], curr, arg_syms, notes)
                val_expr = self._parse_expr_src(st['val_src'], curr, arg_syms, notes)
                if key_expr is None or val_expr is None or var not in curr:
                    notes.append(f"[skip] unparsed store_map: {st}")
                    continue
                curr[var] = If(ok_curr, Store(curr[var], key_expr, val_expr), curr[var])
                continue

            if op == 'store' and 'val_src' in st and 'var' in st:
                var = st['var']
                txt = st['val_src'].strip().rstrip(';')

                # Handle "var = var + rhs"
                m = re.fullmatch(rf"{re.escape(var)}\s*\+\s*(_?[A-Za-z_]\w*)", txt)
                if m and var in curr and not self._is_array(curr[var]):
                    rhs_name = m.group(1)
                    rhs_z = arg_syms.get(rhs_name)
                    if rhs_z is None:
                        rhs_z = BitVec(f"arg.{rhs_name}", 256)
                    curr[var] = If(ok_curr, curr[var] + rhs_z, curr[var])
                    continue

                # Handle "var = var - rhs"
                m = re.fullmatch(rf"{re.escape(var)}\s*\-\s*(_?[A-Za-z_]\w*)", txt)
                if m and var in curr and not self._is_array(curr[var]):
                    rhs_name = m.group(1)
                    rhs_z = arg_syms.get(rhs_name)
                    if rhs_z is None:
                        rhs_z = BitVec(f"arg.{rhs_name}", 256)
                    curr[var] = If(ok_curr, curr[var] - rhs_z, curr[var])
                    continue

                # Fallback: existing expr parser
                val_expr = self._parse_expr_src(txt, curr, arg_syms, notes)
                if val_expr is None or var not in curr:
                    notes.append(f"[skip] unparsed store: {st}")
                    continue
                curr[var] = If(ok_curr, val_expr, curr[var])
                continue

            if op == 'external_call' and 'target_src' in st:
                tgt = self._parse_expr_src(st['target_src'], curr, arg_syms, notes)
                if tgt is not None:
                    meta['target'] = tgt
                    meta['call_depth'] = meta['call_depth'] + BitVecVal(1, 256)
                else:
                    notes.append(f"[skip] unparsed external_call: {st}")
                continue

            # --- Translate raw "+= / -=" updates ---
            if op == 'raw' and 'src' in st:
                src = st['src'].strip().rstrip(';')

                if src.lower() == 'true':
                    continue

                def _addr_key(key_txt: str):
                    z = self._parse_expr_src(key_txt, curr, arg_syms, notes)
                    if z is not None:
                        return z
                    if key_txt in arg_syms:
                        return arg_syms[key_txt]
                    if key_txt in ('msg.sender', 'msg_sender', 'sender'):
                        return BitVec("meta.sender", 160)
                    return BitVec(f"arg.{key_txt}", 160)

                def _u256(rhs_txt: str):
                    z = self._parse_expr_src(rhs_txt, curr, arg_syms, notes)
                    if z is not None:
                        return z
                    if rhs_txt in arg_syms:
                        return arg_syms[rhs_txt]
                    return BitVec(f"arg.{rhs_txt}", 256)

                # balances[key] -= rhs
                m = re.fullmatch(r'([A-Za-z_]\w*)\s*\[\s*([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)\s*\]\s*-\=\s*([A-Za-z_]\w*)', src)
                if m and m.group(1) in curr:
                    arr, key_txt, rhs_txt = m.group(1), m.group(2), m.group(3)
                    key_z = _addr_key(key_txt)
                    rhs_z = _u256(rhs_txt)
                    base = Select(curr[arr], key_z)
                    curr[arr] = If(ok_curr, Store(curr[arr], key_z, base - rhs_z), curr[arr])
                    continue

                # balances[key] += rhs
                m = re.fullmatch(r'([A-Za-z_]\w*)\s*\[\s*([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)\s*\]\s*\+\=\s*([A-Za-z_]\w*)', src)
                if m and m.group(1) in curr:
                    arr, key_txt, rhs_txt = m.group(1), m.group(2), m.group(3)
                    key_z = _addr_key(key_txt)
                    rhs_z = _u256(rhs_txt)
                    base = Select(curr[arr], key_z)
                    curr[arr] = If(ok_curr, Store(curr[arr], key_z, base + rhs_z), curr[arr])
                    continue

                # scalar += rhs
                m = re.fullmatch(r'([A-Za-z_]\w*)\s*\+\=\s*([A-Za-z_]\w*)', src)
                if m:
                    var, rhs_txt = m.group(1), m.group(2)
                    if var in curr and not self._is_array(curr[var]):
                        rhs_z = arg_syms[rhs_txt] if rhs_txt in arg_syms else BitVec(f"arg.{rhs_txt}", 256)
                        curr[var] = If(ok_curr, curr[var] + rhs_z, curr[var])
                        continue

                # scalar -= rhs
                m = re.fullmatch(r'([A-Za-z_]\w*)\s*\-\=\s*([A-Za-z_]\w*)', src)
                if m:
                    var, rhs_txt = m.group(1), m.group(2)
                    if var in curr and not self._is_array(curr[var]):
                        rhs_z = arg_syms[rhs_txt] if rhs_txt in arg_syms else BitVec(f"arg.{rhs_txt}", 256)
                        curr[var] = If(ok_curr, curr[var] - rhs_z, curr[var])
                        continue

                notes.append(f"[raw] {st['src']}")
                continue

            # unknown statement
            notes.append(f"[skip] unknown statement shape: {st}")

        # 6) bind post == curr; collect assumptions
        assumptions = []
        for name in post:
            assumptions.append(post[name] == curr[name])
        # success/revert flag exposure
        assumptions.append(meta['revert_taken'] == Not(ok_curr))

        return SymFunctionModel(
            contract_name=cir.name,
            function_name=fn.name,
            pre=pre, post=post, meta=meta,
            assumptions=assumptions,
            arg_symbols=arg_syms,
            notes=notes
        )

    # ------------------------------------------------------------------
    # Helpers: make storage symbols
    # ------------------------------------------------------------------
    def _mk_state_symbols(self, state_vars) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        pre, post = {}, {}
        for v in state_vars:
            if getattr(v, 'is_mapping', False):
                key_sort = self._sort_for(getattr(v, 'key_ty', 'address'))
                val_sort = self._sort_for(getattr(v, 'val_ty', 'uint256'))
                pre[v.name]  = Array(v.name, key_sort, val_sort)
                post[v.name] = Array(v.name + "1", key_sort, val_sort)
            else:
                s = self._sort_for(getattr(v, 'ty', 'uint256'))
                if s is BV256:
                    pre[v.name]  = BitVec(v.name, 256)
                    post[v.name] = BitVec(v.name + "1", 256)
                elif s is BV160:
                    pre[v.name]  = BitVec(v.name, 160)
                    post[v.name] = BitVec(v.name + "1", 160)
                else:
                    pre[v.name]  = Bool(v.name)
                    post[v.name] = Bool(v.name + "1")
        return pre, post

    def _sort_for(self, ty: str):
        t = (ty or '').strip()
        if t == 'uint' or t == 'uint256': return BV256
        if t == 'address': return BV160
        if t == 'bool': return Bool
        # default numeric
        return BV256

    # ------------------------------------------------------------------
    # Structured IR expression evaluator
    # ------------------------------------------------------------------
    def _E(self, expr: Any, curr: Dict[str, Any], args: Dict[str, Any]):
        """
        Evaluate structured Tiny-IR expressions into Z3 terms.
        Supported ops: 'arg', 'const_uint', 'const_bool', 'const_addr', 'load',
                       'add','sub','UGE','ULE','EQ','NEQ'
        """
        if isinstance(expr, (int,)):
            return BitVecVal(int(expr), 256)
        if isinstance(expr, str):
            # bare names: try args first, then state scalar
            if expr in args: return args[expr]
            if expr in curr and not self._is_array(curr[expr]): return curr[expr]
            # hex address?
            s = expr.strip()
            if s.startswith("0x"):
                return BitVecVal(int(s, 16), 160)
            # fallback: numeric
            if s.isdigit():
                return BitVecVal(int(s), 256)
            # unknown symbol -> create a 256-bit
            return BitVec(expr, 256)

        if isinstance(expr, tuple):
            tag = expr[0]
            if tag == 'arg':
                return args[expr[1]]
            if tag == 'const_uint':
                return BitVecVal(int(expr[1]), 256)
            if tag == 'const_bool':
                return BoolVal(bool(expr[1]))
            if tag == 'const_addr':
                return BitVecVal(int(expr[1], 16), 160)
            if tag == 'load':
                var = expr[1]; key = self._E(expr[2], curr, args)
                return Select(curr[var], key)
            if tag == 'add':
                return self._E(expr[1], curr, args) + self._E(expr[2], curr, args)
            if tag == 'sub':
                return self._E(expr[1], curr, args) - self._E(expr[2], curr, args)
            if tag == 'UGE':
                return UGE(self._E(expr[1], curr, args), self._E(expr[2], curr, args))
            if tag == 'ULE':
                return ULE(self._E(expr[1], curr, args), self._E(expr[2], curr, args))
            if tag == 'EQ':
                return self._E(expr[1], curr, args) == self._E(expr[2], curr, args)
            if tag == 'NEQ':
                return self._E(expr[1], curr, args) != self._E(expr[2], curr, args)
            raise RuntimeError(f"Unsupported IR expr tuple: {expr}")

        # dict or other shapes not supported yet
        raise RuntimeError(f"Unsupported IR expr: {expr!r}")

    def _is_array(self, z):
        # crude check: Arrays don’t support .size(); rely on Python type name
        return hasattr(z, 'sexpr') and z.sort().kind() == ArraySort(BV160, BV256).kind()

    # ------------------------------------------------------------------
    # Heuristic parsers for coarse Slither strings (common ERC-20 cases)
    # ------------------------------------------------------------------
    def _parse_cond_src(self, s: str, curr, args, notes) -> Optional[Any]:
        # Normalize Slither-ish strings like:
        #   "bool,string)(balances[msg.sender] >= amount,Not enough balance)"
        # → "balances[msg.sender] >= amount"
        txt = s.strip()

        # 1) Keep only the substring after the LAST '('
        if "(" in txt:
            txt = txt.rsplit("(", 1)[-1].strip()
        # 2) Drop trailing ')'
        if txt.endswith(")"):
            txt = txt[:-1].strip()
        # 3) Drop revert-message after the LAST comma
        if "," in txt:
            txt = txt.rsplit(",", 1)[0].strip()

        # require(!paused)
        m = re.fullmatch(r'!\s*paused', txt)
        if m and 'paused' in curr:
            return Not(curr['paused'])

        # require(paused == false)
        m = re.fullmatch(r'paused\s*==\s*false', txt, flags=re.IGNORECASE)
        if m and 'paused' in curr:
            return Not(curr['paused'])

        # require(balances[someKey] >= rhs)
        m = re.fullmatch(r'([A-Za-z_]\w*)\s*\[\s*([A-Za-z_][\w\.]*)\s*\]\s*>=\s*([A-Za-z_]\w*)', txt)
        if m:
            arr, key, rhs = m.group(1), m.group(2), m.group(3)
            if arr in curr:
                # key_z
                if key in ('msg.sender', 'msg_sender'):
                    key_z = BitVec("meta.sender", 160)
                else:
                    key_z = args.get(key)
                    if key_z is None:
                        key_z = BitVec(f"arg.{key}", 160)
                # rhs_z
                rhs_z = args.get(rhs)
                if rhs_z is None:
                    rhs_z = BitVec(f"arg.{rhs}", 256)
                return UGE(Select(curr[arr], key_z), rhs_z)

        # require(balances[_from] >= _value) etc. (underscore-prefixed)
        m = re.fullmatch(r'([A-Za-z_]\w*)\s*\[\s*(_?[A-Za-z_][\w\.]*)\s*\]\s*>=\s*(_?[A-Za-z_]\w*)', txt)
        if m:
            arr, key, rhs = m.group(1), m.group(2), m.group(3)
            if arr in curr:
                if key in ('msg.sender', 'msg_sender'):
                    key_z = BitVec("meta.sender", 160)
                else:
                    key_z = args.get(key)
                    if key_z is None:
                        key_z = BitVec(f"arg.{key}", 160)
                rhs_z = args.get(rhs)
                if rhs_z is None:
                    rhs_z = BitVec(f"arg.{rhs}", 256)
                return UGE(Select(curr[arr], key_z), rhs_z)

        notes.append(f"[heuristics] unknown require cond: {s}")
        return None

    def _parse_expr_src(self, s: str, curr, args, notes) -> Optional[Any]:
        """
        Heuristic parser for small source snippets into Z3 terms.
        Supports:
        - msg.sender
        - bool literals
        - address literals (0x..)
        - mapping selects like balances[a]
        - mapping +/- updates like balances[a] + amt
        - plain identifiers (args or scalars in state)
        - numeric literals
        - simple binary comparisons: >, <, >=, <=, ==, != (with optional outer parens)
        """
        from z3 import BitVec, BitVecVal, BoolVal, Select, is_bv, UGT, ULT, UGE, ULE

        txt = (s or "").strip()
        if not txt:
            return None

        # recognize msg.sender
        if txt in ('msg.sender', 'msg_sender', 'sender'):
            return BitVec("meta.sender", 160)

        # bool literals
        if txt.lower() == 'true':
            return BoolVal(True)
        if txt.lower() == 'false':
            return BoolVal(False)

        # address literal like 0xabc...
        if txt.startswith('0x') and len(txt) >= 3:
            try:
                return BitVecVal(int(txt, 16), 160)
            except Exception:
                pass

        # balances[key]
        m = re.fullmatch(r'([A-Za-z_]\w*)\s*\[\s*(_?[A-Za-z_]\w*)\s*\]', txt)
        if m:
            arr, key = m.group(1), m.group(2)
            if arr in curr:
                if key in ('msg.sender', 'msg_sender', 'sender'):
                    key_z = BitVec("meta.sender", 160)
                else:
                    key_z = args.get(key)
                    if key_z is None:
                        key_z = BitVec(f"arg.{key}", 160)
                return Select(curr[arr], key_z)

        # balances[key] +/- amt
        m = re.fullmatch(r'([A-Za-z_]\w*)\s*\[\s*(_?[A-Za-z_]\w*)\s*\]\s*([\+\-])\s*(_?[A-Za-z_]\w*)', txt)
        if m:
            arr, key, op, rhs = m.group(1), m.group(2), m.group(3), m.group(4)
            if arr in curr:
                if key in ('msg.sender', 'msg_sender', 'sender'):
                    key_z = BitVec("meta.sender", 160)
                else:
                    key_z = args.get(key)
                    if key_z is None:
                        key_z = BitVec(f"arg.{key}", 160)
                base = Select(curr[arr], key_z)
                rhs_z = args.get(rhs)
                if rhs_z is None:
                    rhs_z = BitVec(f"arg.{rhs}", 256)
                return base + rhs_z if op == '+' else base - rhs_z

        # plain identifier: arg or state scalar
        if txt in args:
            return args[txt]
        if txt in curr and not self._is_array(curr[txt]):
            return curr[txt]

        # numeric literal
        if txt.isdigit():
            return BitVecVal(int(txt), 256)

        # ---- simple binary comparisons (allow outer parens) ----
        t = txt
        if t.startswith("(") and t.endswith(")"):
            t = t[1:-1].strip()

        m = re.match(r"^(.+?)\s*(>=|<=|==|!=|>|<)\s*(.+)$", t)
        if m:
            lhs_txt, op, rhs_txt = m.group(1).strip(), m.group(2), m.group(3).strip()

            # recursively parse lhs/rhs; fallback to 256-bit symbols/numbers
            lhs = self._parse_expr_src(lhs_txt, curr, args, notes)
            if lhs is None:
                lhs = BitVecVal(int(lhs_txt), 256) if lhs_txt.isdigit() else BitVec(f"arg.{lhs_txt}", 256)

            rhs = self._parse_expr_src(rhs_txt, curr, args, notes)
            if rhs is None:
                rhs = BitVecVal(int(rhs_txt), 256) if rhs_txt.isdigit() else BitVec(f"arg.{rhs_txt}", 256)

            # Use unsigned comparators for bit-vectors (to match invariant_manager._encode_expr)
            if op == ">":
                return UGT(lhs, rhs) if (is_bv(lhs) or is_bv(rhs)) else (lhs > rhs)
            if op == "<":
                return ULT(lhs, rhs) if (is_bv(lhs) or is_bv(rhs)) else (lhs < rhs)
            if op == ">=":
                return UGE(lhs, rhs) if (is_bv(lhs) or is_bv(rhs)) else (lhs >= rhs)
            if op == "<=":
                return ULE(lhs, rhs) if (is_bv(lhs) or is_bv(rhs)) else (lhs <= rhs)
            if op == "==":
                return lhs == rhs
            if op == "!=":
                return lhs != rhs

        # Fallback
        notes.append(f"[heuristics] unknown expr: {s}")
        return None

    # ------------------------------------------------------------------
    # Merging & blocks
    # ------------------------------------------------------------------
    def _merge_states(self, cond, s_then: Dict[str, Any], s_else: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pointwise merge of two post-states under a boolean condition:
        out[k] = If(cond, s_then[k], s_else[k])
        """
        from z3 import If
        out: Dict[str, Any] = {}
        # assume both states have same keys (we build them from the same 'curr' skeleton)
        for k in s_then.keys():
            out[k] = If(cond, s_then[k], s_else[k])
        return out

    def _encode_block(
        self,
        stmts: List[Dict[str, Any]],
        curr_state: Dict[str, Any],
        pc,                         # current path condition (BoolRef)
        args: Dict[str, Any],
        notes_list: List[str],
    ):
        """
        Encode a sequence of coarse IR statements (used for if-then / if-else bodies).
        Mirrors the top-level semantics: guarded updates with pc.
        Returns: (new_state, new_pc)
        """
        from z3 import And, If, Store, Select, BitVec, BitVecVal, BoolVal

        local = dict(curr_state)
        ok_local = pc

        for st in stmts:
            opb = st.get('op')

            # --- require(cond) structured ---
            if opb == 'require' and 'cond' in st:
                condb = self._E(st['cond'], local, args)
                ok_local = And(ok_local, condb)
                continue

            # --- require(cond_src) coarse ---
            if opb == 'require' and 'cond_src' in st:
                txt = st['cond_src'].strip()
                if ")(" in txt:
                    txt = txt.split(")(", 1)[1].strip()
                if "," in txt:
                    txt = txt.rsplit(",", 1)[0].strip()
                txt = txt.replace("msg.sender", "msg_sender")
                condb = self._parse_cond_src(txt, local, args, notes_list)
                if condb is None:
                    # generic expr fallback (e.g., "x > 10")
                    condb = self._parse_expr_src(txt, local, args, notes_list)
                if condb is not None:
                    ok_local = And(ok_local, condb)
                else:
                    notes_list.append(f"[skip] unparsed require (block): {st['cond_src']}")
                continue

            # --- mapping store: balances[a] = val (structured) ---
            if opb == 'store_map' and all(k in st for k in ('var','key','val')):
                var = st['var']
                key = self._E(st['key'], local, args)
                val = self._E(st['val'], local, args)
                if var not in local:
                    notes_list.append(f"[skip] unknown mapping var '{var}' (block)")
                    continue
                local[var] = If(ok_local, Store(local[var], key, val), local[var])
                continue

            # --- mapping store (coarse) ---
            if opb == 'store_map' and 'key_src' in st and 'val_src' in st and 'var' in st:
                var = st['var']
                key_expr = self._parse_expr_src(st['key_src'], local, args, notes_list)
                val_expr = self._parse_expr_src(st['val_src'], local, args, notes_list)
                if key_expr is None or val_expr is None or var not in local:
                    notes_list.append(f"[skip] unparsed store_map (block): {st}")
                    continue
                local[var] = If(ok_local, Store(local[var], key_expr, val_expr), local[var])
                continue

            # --- scalar store: x = <val> (structured) ---
            if opb == 'store' and all(k in st for k in ('var', 'val')):
                var = st['var']
                val = self._E(st['val'], local, args)
                if var not in local:
                    notes_list.append(f"[skip] unknown var '{var}' (block)")
                    continue
                local[var] = If(ok_local, val, local[var])
                continue

            # --- scalar store: x = <val_src> (coarse) ---
            if opb == 'store' and 'val_src' in st and 'var' in st:
                var = st['var']
                txt = st['val_src'].strip().rstrip(';')

                # Match "var = var + rhs" / "var = var - rhs" with optional parens
                m = re.fullmatch(rf"\(?\s*{re.escape(var)}\s*([+\-])\s*(_?[A-Za-z_]\w*)\s*\)?", txt)
                if m and var in local and not self._is_array(local[var]):
                    sign, rhs_name = m.group(1), m.group(2)
                    rhs_z = args.get(rhs_name) or BitVec(f"arg.{rhs_name}", 256)
                    local[var] = If(ok_local,
                                    local[var] + rhs_z if sign == '+' else local[var] - rhs_z,
                                    local[var])
                    continue

                # Fallback: generic expr
                val_expr = self._parse_expr_src(txt, local, args, notes_list)
                if val_expr is None or var not in local:
                    notes_list.append(f"[skip] unparsed store (block): {st}")
                    continue
                local[var] = If(ok_local, val_expr, local[var])
                continue

            # --- external_call (no storage effect; you can tag meta here if needed) ---
            if opb == 'external_call':
                tgt = None
                if 'target' in st:
                    tgt = self._E(st['target'], local, args)
                elif 'target_src' in st:
                    tgt = self._parse_expr_src(st['target_src'], local, args, notes_list)
                if tgt is None:
                    notes_list.append(f"[skip] unparsed external_call (block): {st}")
                # else: ignore storage effect here
                continue

            # --- raw statements (+= / -=; mapping and scalar) ---
            if opb == 'raw' and 'src' in st:
                src = st['src'].strip().rstrip(';')

                if src.lower() == 'true':
                    continue

                def _addr_key(key_txt: str):
                    z = self._parse_expr_src(key_txt, local, args, notes_list)
                    if z is not None:
                        return z
                    if key_txt in args:
                        return args[key_txt]
                    if key_txt in ('msg.sender', 'msg_sender', 'sender'):
                        return BitVec("meta.sender", 160)
                    return BitVec(f"arg.{key_txt}", 160)

                def _u256(rhs_txt: str):
                    z = self._parse_expr_src(rhs_txt, local, args, notes_list)
                    if z is not None:
                        return z
                    if rhs_txt in args:
                        return args[rhs_txt]
                    return BitVec(f"arg.{rhs_txt}", 256)

                # balances[key] -= rhs
                m = re.fullmatch(r'([A-Za-z_]\w*)\s*\[\s*([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)\s*\]\s*-\=\s*([A-Za-z_]\w*)', src)
                if m and m.group(1) in local:
                    arr, key_txt, rhs_txt = m.group(1), m.group(2), m.group(3)
                    key_z = _addr_key(key_txt)
                    rhs_z = _u256(rhs_txt)
                    base = Select(local[arr], key_z)
                    local[arr] = If(ok_local, Store(local[arr], key_z, base - rhs_z), local[arr])
                    continue

                # balances[key] += rhs
                m = re.fullmatch(r'([A-Za-z_]\w*)\s*\[\s*([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)\s*\]\s*\+\=\s*([A-Za-z_]\w*)', src)
                if m and m.group(1) in local:
                    arr, key_txt, rhs_txt = m.group(1), m.group(2), m.group(3)
                    key_z = _addr_key(key_txt)
                    rhs_z = _u256(rhs_txt)
                    base = Select(local[arr], key_z)
                    local[arr] = If(ok_local, Store(local[arr], key_z, base + rhs_z), local[arr])
                    continue

                # scalar += rhs  (e.g., totalSupply += x)
                m = re.fullmatch(r'([A-Za-z_]\w*)\s*\+\=\s*([A-Za-z_]\w*)', src)
                if m:
                    var, rhs_txt = m.group(1), m.group(2)
                    if var in local and not self._is_array(local[var]):
                        rhs_z = args.get(rhs_txt)
                        if rhs_z is None:
                            rhs_z = BitVec(f"arg.{rhs_txt}", 256)

                        local[var] = If(ok_local, local[var] + rhs_z, local[var])
                        continue

                # scalar -= rhs
                m = re.fullmatch(r'([A-Za-z_]\w*)\s*\-\=\s*([A-Za-z_]\w*)', src)
                if m:
                    var, rhs_txt = m.group(1), m.group(2)
                    if var in local and not self._is_array(local[var]):
                        rhs_z = args.get(rhs_txt)
                        if rhs_z is None:
                            rhs_z = BitVec(f"arg.{rhs_txt}", 256)

                        local[var] = If(ok_local, local[var] - rhs_z, local[var])
                        continue

                notes_list.append(f"[raw-block] {st['src']}")
                continue

            # --- nested if inside block ---
            if opb == 'if':
                cond_b = None
                if 'cond' in st:
                    cond_b = self._E(st['cond'], local, args)
                elif 'cond_src' in st:
                    cond_b = self._parse_cond_src(st['cond_src'], local, args, notes_list)
                    if cond_b is None:
                        cond_b = self._parse_expr_src(st['cond_src'], local, args, notes_list)
                if cond_b is None:
                    notes_list.append(f"[skip] unparsed nested if cond: {st.get('cond_src')}")
                    continue

                then_state_b, _ = self._encode_block(st.get('then', []), dict(local), ok_local, args, notes_list)
                else_state_b, _ = self._encode_block(st.get('else', []), dict(local), ok_local, args, notes_list)
                local = self._merge_states(cond_b, then_state_b, else_state_b)
                continue

            # --- unknown ---
            notes_list.append(f"[skip] unknown statement shape (block): {st}")

        return local, ok_local
