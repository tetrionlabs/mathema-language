# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Structural induction over a recursive row language, the derive
strategy a recursive `RowLanguage` supplies for claims quantified over
it (`for t in L[myapp.Node, depth <= 20], size(t) >= 1`).

The claim class, stated so the route never reaches past it:

- the language's root record type refers to itself through one list
  field (its children);
- every function the claim applies to the parameter is a structural
  fold: its body is one `return` of arithmetic over the node's numeric
  fields and aggregates over its children, `sum(g(c) for c in
  t.children)`, `max((g(c) for c in t.children), default=d)`,
  `min(...)`, `len(t.children)`, where each `g` is itself such a fold;
- the claim is one of: a fold against a constant (`size(t) >= 1`); two
  folds related affinely by `==` (`double(t) == 2 * size(t)`); or two
  folds related by an ordering where both aggregate with `sum`.

The proof: at a node with k children, each aggregate is replaced by a
symbol constrained by the induction hypothesis aggregated soundly over
the children (every child's `g(c) >= 1` gives a sum of `k + u`, u >= 0,
and a max of `1 + u` when k >= 1), and the claim at the node is proven
for the base case (k = 0, where the aggregates take their empty values)
and the step (k >= 1). A numeric field enters at its lower bound plus a
nonnegative amount. Anything outside the class returns a result naming
why, never a disproof: an induction that does not go through says
nothing against the claim.

The functions are recursive Python, two stack frames per record level,
so a proof stands only when the language's depth bound keeps that under
the interpreter's recursion limit; over an unbounded language the
mathematics is settled and the implementation is not, and the result
says so, leaving the verdict to execution.
"""
from __future__ import annotations

import ast
import inspect
import sys
import textwrap
from typing import Any

import sympy

from ._surface import ProofResult

_AGGREGATES = ("sum", "max", "min")
_MARGIN = 100
#: a fold recurses through a generator over the children, two frames
#: per record level
_FRAMES_PER_LEVEL = 2


def _deepest_provable() -> int:
    """The largest record depth whose recursion stays under the limit."""
    return max(1, (sys.getrecursionlimit() - _MARGIN) // _FRAMES_PER_LEVEL - 2)


class _NotAFold(Exception):
    """The function or claim is outside the class this route proves."""


class _Fold:
    """One structural fold: its name, parameter, and body as a sympy
    expression over field symbols, aggregate symbols and `k`."""

    def __init__(self, name: str, param: str, body: Any, defaults: dict[str, Any]) -> None:
        self.name, self.param, self.body, self.defaults = name, param, body, defaults


def _function_ast(fn: Any) -> ast.FunctionDef:
    try:
        source = textwrap.dedent(inspect.getsource(fn))
    except (OSError, TypeError) as e:
        raise _NotAFold(f"the source of {getattr(fn, '__name__', fn)!r} is not available") from e
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            return node
    raise _NotAFold(f"{getattr(fn, '__name__', fn)!r} is not a plain function")


class _Reader:
    """Reads fold bodies and claim sides into sympy."""

    def __init__(self, edge: str, functions: dict[str, Any], field_symbols: dict[str, Any]) -> None:
        self.edge = edge
        self.functions = functions
        self.field_symbols = field_symbols
        self.k = sympy.Symbol("k", integer=True, nonnegative=True)
        self.aggregates: dict[tuple[str, str], Any] = {}
        self.folds: dict[str, _Fold] = {}
        self.scope: dict[str, Any] = {}

    def fold(self, name: str) -> _Fold:
        if name in self.folds:
            return self.folds[name]
        fn = self.functions.get(name, self.scope.get(name))
        if not callable(fn):
            raise _NotAFold(f"{name!r} is not a function the claim binds")
        for key, value in getattr(fn, "__globals__", {}).items():
            self.scope.setdefault(key, value)
        node = _function_ast(fn)
        if len(node.args.args) != 1:
            raise _NotAFold(f"{name!r} does not take exactly the one value")
        param = node.args.args[0].arg
        body = [s for s in node.body
                if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
        if len(body) != 1 or not isinstance(body[0], ast.Return) or body[0].value is None:
            raise _NotAFold(f"{name!r} is not one return statement")
        placeholder = _Fold(name, param, None, {})
        self.folds[name] = placeholder
        defaults: dict[str, Any] = {}
        placeholder.body = self._expr(body[0].value, param, defaults)
        placeholder.defaults = defaults
        return placeholder

    def _aggregate(self, call: ast.Call, param: str, defaults: dict[str, Any]) -> Any:
        kind = call.func.id if isinstance(call.func, ast.Name) else None
        if kind not in _AGGREGATES or not call.args or not isinstance(call.args[0], ast.GeneratorExp):
            raise _NotAFold(f"{ast.unparse(call)!r} is not an aggregate over the children")
        gen = call.args[0]
        if len(gen.generators) != 1 or gen.generators[0].ifs:
            raise _NotAFold(f"{ast.unparse(call)!r} filters or nests its children")
        comp = gen.generators[0]
        if not (isinstance(comp.target, ast.Name) and isinstance(comp.iter, ast.Attribute)
                and isinstance(comp.iter.value, ast.Name) and comp.iter.value.id == param
                and comp.iter.attr == self.edge):
            raise _NotAFold(f"{ast.unparse(call)!r} does not run over {param}.{self.edge}")
        elt = gen.elt
        if not (isinstance(elt, ast.Call) and isinstance(elt.func, ast.Name) and len(elt.args) == 1
                and isinstance(elt.args[0], ast.Name) and elt.args[0].id == comp.target.id):
            raise _NotAFold(f"{ast.unparse(call)!r} does not apply one function to each child")
        inner = elt.func.id
        self.fold(inner)
        key = (kind, inner)
        if key not in self.aggregates:
            self.aggregates[key] = sympy.Symbol(f"{kind}_{inner}", real=True)
        if kind in ("max", "min"):
            default = None
            for kw in call.keywords:
                if kw.arg == "default":
                    default = self._expr(kw.value, param, defaults)
            if default is None:
                raise _NotAFold(f"{ast.unparse(call)!r} has no default, so it raises on a leaf")
            defaults[f"{kind}_{inner}"] = default
        return self.aggregates[key]

    def _expr(self, node: ast.AST, param: str, defaults: dict[str, Any]) -> Any:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
                and not isinstance(node.value, bool):
            return sympy.nsimplify(node.value)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult)):
            a = self._expr(node.left, param, defaults)
            b = self._expr(node.right, param, defaults)
            return a + b if isinstance(node.op, ast.Add) else a - b if isinstance(node.op, ast.Sub) \
                else a * b
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -self._expr(node.operand, param, defaults)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                and node.value.id == param and node.attr in self.field_symbols:
            return self.field_symbols[node.attr]
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "len" and len(node.args) == 1 \
                    and isinstance(node.args[0], ast.Attribute) and node.args[0].attr == self.edge:
                return self.k
            if node.func.id in _AGGREGATES and node.args and isinstance(node.args[0], ast.GeneratorExp):
                return self._aggregate(node, param, defaults)
        raise _NotAFold(f"{ast.unparse(node)!r} is not arithmetic over fields and children")

    def _canonical(self, name: str) -> str:
        """The function's own name when the claim binds it under another
        (`f` for `size`), so a fold and its recursive calls read as one."""
        fn = self.functions.get(name)
        own = getattr(fn, "__name__", None)
        if own and own != name and getattr(fn, "__globals__", {}).get(own) is fn \
                and self.functions.get(own, fn) is fn:
            self.scope.setdefault(own, fn)
            return str(own)
        return name

    def claim_side(self, text: str, param: str) -> Any:
        """A claim side over fold calls on `param`, each a symbol."""
        node = ast.parse(text, mode="eval").body
        return self._side(node, param)

    def _side(self, node: ast.AST, param: str) -> Any:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and len(node.args) == 1 \
                and isinstance(node.args[0], ast.Name) and node.args[0].id == param:
            name = self._canonical(node.func.id)
            self.fold(name)
            return sympy.Symbol(f"F_{name}", real=True)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
                and not isinstance(node.value, bool):
            return sympy.nsimplify(node.value)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult)):
            a, b = self._side(node.left, param), self._side(node.right, param)
            return a + b if isinstance(node.op, ast.Add) else a - b if isinstance(node.op, ast.Sub) \
                else a * b
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -self._side(node.operand, param)
        raise _NotAFold(f"{ast.unparse(node)!r} is not an expression in folds of {param}")


def _field_symbols(language: Any) -> tuple[dict[str, Any], dict[Any, Any]]:
    """A symbol per numeric field, and each written as its lower bound
    plus a nonnegative amount where it has one."""
    symbols: dict[str, Any] = {}
    shifts: dict[Any, Any] = {}
    for name, bound in (language.fields() or {}).items():
        if bound is None or getattr(bound, "base_type", None) == "L" or hasattr(bound, "name"):
            continue
        sym = sympy.Symbol(name, real=True)
        symbols[name] = sym
        lo = None
        if bound == "N":
            lo = 0
        elif isinstance(bound, tuple) and len(bound) == 2:
            lo = bound[0]
        elif getattr(bound, "pieces", None):
            pieces = [p for p in bound.pieces if isinstance(p, tuple)]
            if pieces:
                lo = min(p[0] for p in pieces)
        if lo is not None and lo != float("-inf"):
            shifts[sym] = sympy.nsimplify(lo) + sympy.Symbol(f"{name}_over", nonnegative=True)
    return symbols, shifts


def _holds(expr: Any, relation: str) -> bool:
    """Whether `expr REL 0` holds for every nonnegative value of its
    free symbols, as sympy can settle it."""
    expr = sympy.expand(expr)
    if relation == "==":
        return bool(sympy.simplify(expr) == 0)
    if relation in (">=",):
        return bool(expr.is_nonnegative)
    if relation == ">":
        return bool(expr.is_positive)
    if relation == "<=":
        return bool((-expr).is_nonnegative)
    if relation == "<":
        return bool((-expr).is_positive)
    return False


def prove(language: Any, param: str, lhs: str, relation: str, rhs: str,
          functions: dict[str, Any], depth_bound: int | None) -> ProofResult | None:
    """Structural induction for one claim, or None when the language is
    not a self-referential record type this route reads."""
    found = language._edge()
    if found is None or found[2] or found[1].type.base != "list":
        return None
    edge = found[1].name
    if relation not in ("==", ">=", ">", "<=", "<"):
        return ProofResult("unliftable", sketch=f"induction reads ==, <=, >=, <, >, not {relation}")
    symbols, shifts = _field_symbols(language)
    reader = _Reader(edge, functions, symbols)
    try:
        claim = reader.claim_side(lhs, param) - reader.claim_side(rhs, param)
        outcome = _induct(reader, claim, relation, shifts)
    except _NotAFold as e:
        return ProofResult("unliftable", sketch=f"induction does not read this claim: {e}")
    if outcome is not None:
        return ProofResult("unliftable", sketch=f"induction does not go through: {outcome}")
    frames = _FRAMES_PER_LEVEL * ((depth_bound or 0) + 1) + _MARGIN
    if depth_bound is None or frames >= sys.getrecursionlimit():
        return ProofResult(
            "undecided",
            sketch=("by structural induction over " + edge + " the mathematics holds (base case and "
                    "step both proven), but the implementation's recursion takes a frame per level and "
                    + ("the language bounds no depth" if depth_bound is None else
                       f"depth {depth_bound} reaches the recursion limit")
                    + ", so a deep enough member raises; bound the depth "
                      f"(L[..., depth <= {_deepest_provable()}]) for a proof"),
            meta={"mathema.derive_route": "induction"})
    return ProofResult(
        "proven",
        sketch=(f"by structural induction over {edge}: the base case (no {edge}) and the step "
                f"(k >= 1 {edge}, the claim assumed of each) both hold, and depth <= {depth_bound} "
                "keeps the recursion under the interpreter's limit"),
        quantifier=f"∀ {param} in the language, by induction over {edge}",
        meta={"mathema.derive_route": "induction"})


def _induct(reader: _Reader, claim: Any, relation: str, shifts: dict[Any, Any]) -> str | None:
    """None when the base case and the step both prove, else the reason
    one does not."""
    folds = sorted((s for s in claim.free_symbols if s.name.startswith("F_")), key=lambda s: s.name)
    if not folds:
        return "the claim applies no fold to the value"
    if any(str(s) not in {f"F_{n}" for n in reader.folds} for s in folds):
        return "the claim mentions something other than folds of the value"
    coeffs = {s: claim.coeff(s) for s in folds}
    constant = sympy.expand(claim - sum(c * s for s, c in coeffs.items()))
    if any(c.free_symbols for c in coeffs.values()) or constant.free_symbols or \
            sympy.expand(sum(c * s for s, c in coeffs.items()) + constant - claim) != 0:
        return "the claim is not affine in its folds"
    names = [s.name[2:] for s in folds]
    u = sympy.Symbol("u", nonnegative=True)
    # the aggregated hypothesis: each aggregate of a claimed fold,
    # constrained by the claim holding at every child
    k1 = sympy.Symbol("k1", integer=True, nonnegative=True)
    step_subs: dict[Any, Any] = {reader.k: 1 + k1}
    base_subs: dict[Any, Any] = {reader.k: 0}
    for (kind, inner), sym in reader.aggregates.items():
        base_subs[sym] = 0 if kind == "sum" else reader.folds[inner].defaults.get(f"{kind}_{inner}", sym)
    if len(names) == 1:
        (name,) = names
        a = coeffs[folds[0]]
        bound = -constant / a
        rel = relation if a > 0 else {">=": "<=", ">": "<", "<=": ">=", "<": ">", "==": "=="}[relation]
        for (kind, inner), sym in reader.aggregates.items():
            if inner != name:
                return f"the fold of {name} aggregates {inner}, which the claim says nothing about"
            if kind == "sum":
                n = 1 + k1
                step_subs[sym] = n * bound + (u if rel in (">=", ">") else -u if rel in ("<=", "<") else 0)
            elif rel in (">=", ">") and kind in ("max", "min"):
                step_subs[sym] = bound + u
            elif rel in ("<=", "<") and kind in ("max", "min"):
                step_subs[sym] = bound - u
            elif rel == "==":
                step_subs[sym] = bound
        node = reader.folds[name].body - bound
        target = rel
    elif len(names) == 2:
        a_sym, b_sym = folds
        alpha, beta = coeffs[a_sym], coeffs[b_sym]
        aggs = {inner: kind for (kind, inner) in reader.aggregates}
        if set(aggs) - set(n for n in names):
            return "a fold aggregates a function the claim says nothing about"
        if any(kind != "sum" for kind in aggs.values()):
            if relation != "==" or any(kind != aggs.get(names[0]) for kind in aggs.values()):
                return "two folds are related only when both aggregate by sum (or by the same max or min under ==)"
            if not bool((-beta / alpha).is_nonnegative):
                return "a max or min carries the hypothesis only through an order-preserving map"
        sa = reader.aggregates.get((aggs.get(names[0], "sum"), names[0]))
        sb = reader.aggregates.get((aggs.get(names[1], "sum"), names[1]))
        if sa is None or sb is None:
            return "each fold must aggregate itself over the children"
        n = 1 + k1
        slack = 0 if relation == "==" else (u if relation in (">=", ">") else -u)
        count = n if aggs.get(names[0]) == "sum" else 1
        step_subs[sa] = (slack - beta * sb - count * constant) / alpha
        node = alpha * reader.folds[names[0]].body + beta * reader.folds[names[1]].body + constant
        target = relation
    else:
        return "the claim relates more than two folds"
    base = sympy.expand(node.subs(base_subs).subs(shifts))
    step = sympy.expand(node.subs(step_subs).subs(shifts))
    if not _holds(base, target):
        return f"the base case (no {reader.edge}) does not prove: {base} {target} 0"
    if not _holds(step, target):
        return f"the step does not prove: {step} {target} 0"
    return None


__all__ = ["prove"]
