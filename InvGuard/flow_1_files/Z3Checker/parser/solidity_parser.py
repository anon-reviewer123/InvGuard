# solidity_parser.py
# Backend-only Solidity → Tiny IR parser
# Prefers: Slither (best) → falls back to py-solc-x (AST-only)
# Produces: ContractIR(state vars, functions with args, and a coarse body)
#
# Usage:
#   from parser.solidity_parser import SolidityParser
#   cir = SolidityParser().parse("/path/to/contract.sol", contract_name=None)
#   print(cir)

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import os
import re
import json
import logging
logging.basicConfig(level=logging.INFO, force=True)

# -----------------------
# Tiny IR (self-contained)
# -----------------------
@dataclass
class VarDecl:
    name: str
    ty: str                   # 'uint256' | 'bool' | 'address' | 'mapping(address=>uint256)' | ...
    is_mapping: bool = False
    key_ty: Optional[str] = None
    val_ty: Optional[str] = None

@dataclass
class FunctionIR:
    name: str
    args: List[VarDecl]
    body: List[Dict[str, Any]]  # list of statements (dicts): require/store/store_map/external_call (coarse)

@dataclass
class ContractIR:
    name: str
    state: List[VarDecl]
    functions: List[FunctionIR]

# -----------------------
# Utilities
# -----------------------
_SIMPLE_TYPE_MAP = {
    "uint": "uint256",
    "uint256": "uint256",
    "bool": "bool",
    "address": "address",
}

def _norm_type(t: str) -> str:
    t = t.strip()
    if t in _SIMPLE_TYPE_MAP:
        return _SIMPLE_TYPE_MAP[t]
    if t.startswith("mapping"):
        return t
    return t

def _map_var_type(solty: str) -> VarDecl:
    solty = solty.strip()
    m = re.match(r"mapping\s*\(\s*([A-Za-z0-9_]+)\s*=>\s*([A-Za-z0-9_]+)\s*\)", solty)
    if m:
        key_t = _norm_type(m.group(1))
        val_t = _norm_type(m.group(2))
        return VarDecl(
            name="", ty=f"mapping({key_t}=>{val_t})",
            is_mapping=True, key_ty=key_t, val_ty=val_t
        )
    return VarDecl(name="", ty=_norm_type(solty))

# -----------------------
# Debug flag
# -----------------------
DEBUG_PARSE = True  # flip to True to see parser debug logs

# -----------------------
# Parser
# -----------------------
class SolidityParser:
    def __init__(self) -> None:
        self._slither = None
        self._solcx = None
        try:
            from slither.slither import Slither  # type: ignore
            self._Slither = Slither
            self._slither = True
        except Exception:
            self._slither = False
        try:
            import solcx  # type: ignore
            self._solcx = solcx
        except Exception:
            self._solcx = None

    def parse(self, filepath: str, contract_name: Optional[str] = None) -> ContractIR:
        if not os.path.exists(filepath):
            raise FileNotFoundError(filepath)

        if self._slither:
            try:
                if DEBUG_PARSE:
                    logging.info("[parser] USING SLITHER path")
                return self._parse_with_slither(filepath, contract_name)
            except Exception as e:
                if DEBUG_PARSE:
                    logging.info(f"[parser] Slither failed: {e}. Falling back to py-solc-x AST…")

        if self._solcx:
            if DEBUG_PARSE:
                logging.info("[parser] USING SOLCX (py-solc-x) path")
            return self._parse_with_solcx(filepath, contract_name)

        raise RuntimeError("Neither Slither nor py-solc-x is available. ...")

    # --------------- Slither path ---------------
    def _parse_with_slither(self, filepath: str, contract_name: Optional[str]) -> ContractIR:
        Slither = self._Slither  # type: ignore
        sl = Slither(filepath)
        c = None
        if contract_name:
            for cc in sl.contracts:
                if cc.name == contract_name:
                    c = cc; break
            if c is None:
                raise ValueError(f"Contract {contract_name} not found. Available: {[cc.name for cc in sl.contracts]}")
        else:
            non_ifaces = [cc for cc in sl.contracts if not cc.is_interface]
            c = non_ifaces[0] if non_ifaces else sl.contracts[0]

        state: List[VarDecl] = []
        for sv in c.state_variables_declared:
            vname = sv.name
            vtype = self._slither_typename(sv.type)
            vd = _map_var_type(vtype)
            vd.name = vname
            state.append(vd)

        funs: List[FunctionIR] = []
        for f in c.functions:
            if f.is_constructor or f.is_fallback or f.is_receive:
                continue
            args = []
            for p in f.parameters:
                args.append(VarDecl(name=p.name or f"arg{len(args)}", ty=_norm_type(self._slither_typename(p.type))))
            body = self._slither_coarse_body(f)
            funs.append(FunctionIR(name=f.name, args=args, body=body))

        return ContractIR(name=c.name, state=state, functions=funs)

    def _slither_typename(self, t) -> str:
        return _norm_type(str(t))

    def _slither_coarse_body(self, f) -> List[Dict[str, Any]]:
        body: List[Dict[str, Any]] = []
        for n in f.nodes:
            s = ""
            try:
                s = getattr(n, "solidity_statement", "") or ""
            except Exception:
                s = ""
            if not s:
                stmt = getattr(n, "content", None) or getattr(n, "expression", None)
                s = (str(stmt) if stmt is not None else "").strip()
            s = (s or "").replace("\r", "\n").strip()
            if not s:
                continue
            if "if" in s and "(" in s:
                if_node = self._parse_if_text(s)
                if if_node is not None:
                    body.append(if_node)
                    continue
            parts = [p for p in s.split("\n") if p.strip()]
            for p in parts:
                body.append(self._coarse_stmt_from_line(p))

        # Safe grouping pass
        import re
        grouped: List[Dict[str, Any]] = []
        i = 0
        def _is_comparison_cond(txt: str) -> bool:
            t = (txt or "").strip()
            if not t:
                return False
            has_comp = any(op in t for op in (">=", "<=", "==", "!=", ">", "<"))
            if not has_comp:
                return False
            if "+=" in t or "-=" in t:
                return False
            if re.search(r'(?<![<>!=])=`?(?![=])', t):
                return False
            if ":=" in t:
                return False
            return True

        while i < len(body):
            st = body[i]
            if st.get("op") == "raw":
                cond_src = st.get("src", "")
                if _is_comparison_cond(cond_src):
                    then_stmt = body[i + 1] if i + 1 < len(body) else None
                    else_stmt = body[i + 2] if i + 2 < len(body) else None
                    if then_stmt and else_stmt:
                        grouped.append({
                            "op": "if",
                            "cond_src": cond_src,
                            "then": [then_stmt],
                            "else": [else_stmt],
                        })
                        i += 3
                        continue
            grouped.append(st)
            i += 1

        body = grouped
        if DEBUG_PARSE:
            logging.info("[DEBUG-body-lines]")
            for st in body:
                logging.info("   %s", st)
        return body

    def _coarse_stmt_from_line(self, s: str) -> dict:
        s = (s or "").strip().rstrip(";")
        if not s:
            return {"op": "raw", "src": ""}
        import re
        m = re.match(r"^require\s*\((.+)\)\s*$", s)
        if m:
            return {'op': 'require', 'cond_src': m.group(1)}
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*\[(.+)\]\s*=\s*(.+)$", s)
        if m:
            return {'op':'store_map','var':m.group(1),'key_src':m.group(2),'val_src':m.group(3)}
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$", s)
        if m and "[" not in m.group(1):
            return {'op':'store','var':m.group(1),'val_src':m.group(2)}
        if ".call(" in s or re.search(r"[A-Za-z_]\w*\.[A-Za-z_]\w*\(", s):
            tgt = s.split(".", 1)[0]
            return {'op':'external_call','target_src':tgt}
        return {'op':'raw','src':s}

    # ... rest unchanged (_consume_if_else_block, _parse_with_solcx, etc.)

    def _consume_if_else_block(self, lines, i):
        import re
        header = lines[i].strip()
        m = re.match(r"^if\s*\((.+)\)\s*(\{)?\s*$", header)
        if not m:
            m2 = re.match(r"^if\s*\((.+)\)\s*(.+?)\s*else\s*(.+?)\s*$", header)
            if m2:
                cond_src = m2.group(1).strip()
                then_st = self._coarse_stmt_from_line(m2.group(2))
                else_st = self._coarse_stmt_from_line(m2.group(3))
                return ({'op':'if','cond_src':cond_src,'then':[then_st],'else':[else_st]}, i+1)
            return (None, i)

        cond_src = m.group(1).strip()
        has_brace = bool(m.group(2))

        def collect_block(j):
            blk = []
            brace = 0
            if "{" in lines[j]:
                brace += lines[j].count("{")
                j += 1
            while j < len(lines):
                line = lines[j]
                brace += line.count("{")
                brace -= line.count("}")
                if brace == 0 and "}" in line:
                    return blk, j+1
                blk.append(line.strip().rstrip(";"))
                j += 1
            return blk, j

        k = i
        then_block, k = collect_block(k) if has_brace else ([lines[i+1].strip().rstrip(";")], i+2)

        while k < len(lines) and not lines[k].strip():
            k += 1

        else_block = []
        if k < len(lines) and lines[k].strip().startswith("else"):
            if "{" in lines[k]:
                else_block, k = collect_block(k)
            else:
                if k+1 < len(lines):
                    else_block = [lines[k+1].strip().rstrip(";")]
                    k = k+2

        then_stmts = [self._coarse_stmt_from_line(x) for x in then_block if x and x != "}"]
        else_stmts = [self._coarse_stmt_from_line(x) for x in else_block if x and x != "}"]
        return ({'op':'if','cond_src':cond_src,'then':then_stmts,'else':else_stmts}, k)

    # --------------- py-solc-x path ---------------
    def _parse_with_solcx(self, filepath: str, contract_name: Optional[str]) -> ContractIR:
        solcx = self._solcx  # type: ignore
        from pathlib import Path
        source_path = Path(filepath)
        source = source_path.read_text(encoding="utf-8")

        solcx.set_solc_version("0.8.20", silent=True)

        input_json = {
            "language": "Solidity",
            "sources": {
                source_path.name: {"content": source}
            },
            "settings": {
                "optimizer": {"enabled": False, "runs": 200},
                "outputSelection": {
                    "*": {
                        "*": ["abi"],
                        "": ["ast"]
                    }
                }
            }
        }

        out = solcx.compile_standard(input_json, allow_paths=".")
        file_out = out["sources"][source_path.name]
        ast = file_out.get("ast")
        if not ast:
            raise RuntimeError("No AST returned from solc.")

        contracts = [n for n in ast.get("nodes", []) if n.get("nodeType") == "ContractDefinition"]
        if not contracts:
            raise RuntimeError("No ContractDefinition found in AST.")
        cnode = None
        if contract_name:
            for n in contracts:
                if n.get("name") == contract_name:
                    cnode = n; break
            if cnode is None:
                raise ValueError(f"Contract {contract_name} not found. Available: {[n.get('name') for n in contracts]}")
        else:
            cnode = contracts[0]

        state: List[VarDecl] = []
        for n in cnode.get("nodes", []):
            if n.get("nodeType") == "VariableDeclaration" and n.get("stateVariable", False):
                vname = n.get("name")
                vtype = self._extract_type_from_ast_typeName(n.get("typeName"))
                vd = _map_var_type(vtype)
                vd.name = vname
                state.append(vd)

        funs: List[FunctionIR] = []
        for n in cnode.get("nodes", []):
            if n.get("nodeType") == "FunctionDefinition" and n.get("kind") in ("function", "public", "external"):
                fname = n.get("name") or ""
                params = n.get("parameters", {}).get("parameters", [])
                args = []
                for p in params:
                    pname = p.get("name") or f"arg{len(args)}"
                    ptype = self._extract_type_from_ast_typeName(p.get("typeName"))
                    args.append(VarDecl(name=pname, ty=_norm_type(ptype)))
                funs.append(FunctionIR(name=fname, args=args, body=[]))

        return ContractIR(name=cnode.get("name", "Contract"), state=state, functions=funs)

    def _pick_solc_version_from_pragma(self, source: str):
        m = re.search(r"pragma\s+solidity\s+([^;]+);", source)
        if not m:
            return None
        return None

    def _extract_type_from_ast_typeName(self, typeName: Optional[dict]) -> str:
        if not typeName:
            return "uint256"
        nt = typeName.get("nodeType")
        if nt == "ElementaryTypeName":
            return typeName.get("name", "uint256")
        if nt == "Mapping":
            key_t = self._extract_type_from_ast_typeName(typeName.get("keyType"))
            val_t = self._extract_type_from_ast_typeName(typeName.get("valueType"))
            return f"mapping({key_t}=>{val_t})"
        if nt == "UserDefinedTypeName":
            return typeName.get("namePath", "uint256")
        return "uint256"

    def _parse_if_text(self, s: str):
        import re
        txt = (s or "").strip()
        if not txt.lstrip().startswith("if"):
            return None
        m = re.match(
            r"^\s*if\s*\((?P<cond>.+?)\)\s*\{\s*(?P<thens>.*?)\s*\}\s*(?:else\s*\{\s*(?P<elses>.*?)\s*\}\s*)?$",
            txt,
            flags=re.DOTALL
        )
        if not m:
            return None

        cond = m.group("cond").strip()
        then_block = (m.group("thens") or "").strip()
        else_block = (m.group("elses") or "").strip()

        has_assignmentish = any(tok in cond for tok in ["+=", "-=", "="])
        has_comparison = any(op in cond for op in [">=", "<=", "==", "!=", ">", "<"])
        if has_assignmentish and not has_comparison:
            return None

        def _split_block(btxt: str):
            lines = []
            for part in re.split(r";|\n", btxt):
                p = part.strip()
                if p:
                    lines.append({"op": "raw", "src": p})
            return lines

        return {
            "op": "if",
            "cond_src": cond,
            "then": _split_block(then_block),
            "else": _split_block(else_block),
        }

# --------------- CLI test ---------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python solidity_parser.py <path-to-solidity> [ContractName]")
        sys.exit(1)
    path = sys.argv[1]
    cname = sys.argv[2] if len(sys.argv) > 2 else None
    cir = SolidityParser().parse(path, cname)
    print("\n=== ContractIR ===")
    print(f"Contract: {cir.name}")
    print("State:")
    for v in cir.state:
        print("  ", v)
    print("Functions:")
    for f in cir.functions:
        print(f"  {f.name}({', '.join([a.ty+' '+a.name for a in f.args])})")
        for st in f.body:
            print("    -", st)
