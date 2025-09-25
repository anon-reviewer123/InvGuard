# model/ir_utils.py
# Utilities for mapping Solidity-like IR types/values to Z3
# Works with your SymModelBuilder and future encoders.

from __future__ import annotations
from typing import Any, Optional, Tuple
import re

try:
    from z3 import (
        Bool, BoolVal, And, Or, Not, If,
        BitVecSort, BitVec, BitVecVal, ArraySort, Array, Store, Select,
        UGE, ULE, UGT, ULT, simplify, is_bv, is_bool
    )
except Exception as e:
    raise RuntimeError("Install z3-solver: pip install z3-solver")


# Canonical EVM widths
BV256 = BitVecSort(256)
BV160 = BitVecSort(160)


# -----------------------------
# Type handling / symbol makers
# -----------------------------

_SIMPLE_TYPE_MAP = {
    "uint": "uint256",
    "uint256": "uint256",
    "bool": "bool",
    "address": "address",
}

def normalize_type(t: str) -> str:
    t = (t or "").strip()
    if t in _SIMPLE_TYPE_MAP:
        return _SIMPLE_TYPE_MAP[t]
    return t  # keep other uintN, custom, or mapping(...) forms as-is


def sort_for(ty: str):
    t = normalize_type(ty)
    if t == "uint256" or t == "uint":
        return BV256
    if t == "address":
        return BV160
    if t == "bool":
        return Bool
    # default numeric
    return BV256


def mk_arg_symbol(name: str, ty: str):
    s = sort_for(ty)
    if s is BV256:
        return BitVec(f"arg.{name}", 256)
    if s is BV160:
        return BitVec(f"arg.{name}", 160)
    return Bool(f"arg.{name}")


def mk_state_symbol(name: str, ty: str, post: bool = False):
    s = sort_for(ty)
    suf = "1" if post else ""
    if s is BV256:
        return BitVec(name + suf, 256)
    if s is BV160:
        return BitVec(name + suf, 160)
    return Bool(name + suf)


def mk_mapping_symbols(name: str, key_ty: str, val_ty: str, post: bool = False):
    key_sort = sort_for(key_ty)
    val_sort = sort_for(val_ty)
    arrname = name + ("1" if post else "")
    return Array(arrname, key_sort, val_sort)


# -----------------------------
# Literals / casting
# -----------------------------

_HEX_ADDR = re.compile(r"^0x[0-9a-fA-F]{1,40}$")

def addr_const(s: str):
    """
    Accepts hex like '0xabc...'; normalizes to 160-bit BitVec immediate.
    """
    if not isinstance(s, str) or not _HEX_ADDR.match(s.strip()):
        raise ValueError(f"Not a hex address: {s!r}")
    return BitVecVal(int(s, 16), 160)


def uint_const(v: int) -> Any:
    """
    Return 256-bit BitVec immediate for unsigned literals.
    """
    if not isinstance(v, int):
        raise TypeError("uint_const expects int")
    return BitVecVal(v & ((1 << 256) - 1), 256)


def bool_const(b: bool) -> Any:
    return BoolVal(bool(b))


def to_bool(x: Any) -> Any:
    """
    Coerce BitVec to Bool via != 0 when needed.
    """
    if is_bool(x):
        return x
    if is_bv(x):
        return x != uint_const(0)
    # Fallback: treat as truthy?
    return x


# -----------------------------
# Unsigned comparators (wrappers)
# -----------------------------

def uge(a, b): return UGE(a, b)
def ule(a, b): return ULE(a, b)
def ugt(a, b): return UGT(a, b)
def ult(a, b): return ULT(a, b)


# -----------------------------
# Mapping (Solidity mapping => Z3 Array)
# -----------------------------

def arr_select(arr, key):  # balances[address]
    return Select(arr, key)

def arr_store(arr, key, val):  # balances[address] = val
    return Store(arr, key, val)


# -----------------------------
# Small parser helpers (string → Z3), optional use
# -----------------------------

_IDENT = r"[A-Za-z_]\w*"

def parse_uint_or_addr_literal(tok: str) -> Optional[Any]:
    t = tok.strip()
    if t.isdigit():
        return uint_const(int(t))
    if _HEX_ADDR.match(t):
        return addr_const(t)
    return None


def parse_indexed_access(src: str, env_state: dict, env_args: dict) -> Optional[Any]:
    """
    balances[sender]   → Select(curr['balances'], arg/symbol 'sender')
    """
    m = re.fullmatch(rf"({_IDENT})\s*\[\s*({_IDENT})\s*\]", src.strip())
    if not m:
        return None
    arr, key = m.group(1), m.group(2)
    if arr not in env_state:
        return None
    key_z = env_args.get(key) or BitVec(f"arg.{key}", 160)
    return Select(env_state[arr], key_z)


def parse_indexed_affine(src: str, env_state: dict, env_args: dict) -> Optional[Any]:
    """
    balances[sender] +/- amt
    """
    m = re.fullmatch(rf"({_IDENT})\s*\[\s*({_IDENT})\s*\]\s*([+\-])\s*({_IDENT})", src.strip())
    if not m:
        return None
    arr, key, op, rhs = m.group(1), m.group(2), m.group(3), m.group(4)
    if arr not in env_state:
        return None
    key_z = env_args.get(key) or BitVec(f"arg.{key}", 160)
    base = Select(env_state[arr], key_z)
    rhs_z = env_args.get(rhs) or BitVec(f"arg.{rhs}", 256)
    return base + rhs_z if op == '+' else base - rhs_z


def parse_simple_expr(src: str, env_state: dict, env_args: dict) -> Optional[Any]:
    """
    Very small expression parser used by SymModelBuilder fallback heuristics.
    Handles:
        - bool literals: true/false
        - uint/address literals: 123, 0xabc...
        - identifiers: arg or scalar state vars
        - balances[key] and balances[key] +/- amt
    Extend as needed.
    """
    s = src.strip()

    # bools
    if s.lower() == "true":  return BoolVal(True)
    if s.lower() == "false": return BoolVal(False)

    # numerics or address
    lit = parse_uint_or_addr_literal(s)
    if lit is not None:
        return lit

    # balances[key]
    e = parse_indexed_access(s, env_state, env_args)
    if e is not None:
        return e

    # balances[key] +/- amt
    e = parse_indexed_affine(s, env_state, env_args)
    if e is not None:
        return e

    # plain identifiers
    if s in env_args:
        return env_args[s]
    if s in env_state and not _is_array(env_state[s]):
        return env_state[s]

    return None


def parse_geq_balances_pattern(src: str, env_state: dict, env_args: dict) -> Optional[Any]:
    """
    Recognize: balances[sender] >= amt
    Returns a BoolRef (UGE(...)).
    """
    m = re.fullmatch(rf"({_IDENT})\s*\[\s*({_IDENT})\s*\]\s*>=\s*({_IDENT})", src.strip())
    if not m:
        return None
    arr, key, rhs = m.group(1), m.group(2), m.group(3)
    if arr not in env_state:
        return None
    key_z = env_args.get(key) or BitVec(f"arg.{key}", 160)
    rhs_z = env_args.get(rhs) or BitVec(f"arg.{rhs}", 256)
    return UGE(Select(env_state[arr], key_z), rhs_z)


# -----------------------------
# Misc helpers
# -----------------------------

def _is_array(z) -> bool:
    try:
        return z.sort().kind() == ArraySort(BV160, BV256).kind()
    except Exception:
        return False


def ensure_bv160(x: Any) -> Any:
    if is_bv(x) and x.size() == 160:
        return x
    if isinstance(x, str) and _HEX_ADDR.match(x):
        return addr_const(x)
    # best effort cast (may be lossy)
    return x


def ensure_bv256(x: Any) -> Any:
    if is_bv(x) and x.size() == 256:
        return x
    # attempt int cast
    try:
        return uint_const(int(str(x)))
    except Exception:
        return x

