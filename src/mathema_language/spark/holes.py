# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""What a Spark column rule gives when an input column holds a hole,
and how it got there. For each column the rule reads and each hole that
column admits (`null`, and `nan` for a floating-point column), the rule
is evaluated with that column a hole and every other column unknown,
with Spark's semantics: a comparison with null is null, a `when` whose
condition is null or false is skipped, NaN is above every number and
equal to itself, and null passes through arithmetic.

The outcome is explicit when the branch that fires tests for the hole
(`isNull`, `isNotNull`, `isnan`, or a `coalesce` that skips it),
implicit when the engine decided it (the rule fell through to
`otherwise`, NaN compared as the largest number, null passed through
arithmetic), and conditional when it depends on another column."""
from __future__ import annotations

import ast
import math
import operator
from dataclasses import dataclass
from typing import Any

from .lower import (
    _COL,
    _LIT,
    NotRead,
    _call_name,
    _columns_set,
    _constants,
    _defaults,
    _function,
    _source,
    _text,
)

#: the values a condition takes: true, false, null, and unknown when it
#: depends on a column other than the hole
T, F, N, U = "true", "false", "null", "unknown"

#: a value that depends on a column other than the hole
OTHER = object()


@dataclass(frozen=True)
class HoleOutcome:
    """What the rule gives at one hole of one input column. `output` is
    the value written, `None` for a null; `how` is "explicit",
    "implicit" or "conditional"; `because` says which construct handled
    the hole or why the engine decided it; `possible` lists the outputs
    a conditional outcome can take."""
    column: str
    member: str
    output: Any
    how: str
    because: str
    possible: tuple[Any, ...] = ()

    @property
    def propagates(self) -> bool:
        """Whether the hole comes out as a hole in the output."""
        return self.how != "conditional" and self.output is None

    def sentence(self) -> str:
        """The record's sentence for this outcome."""
        given = "null" if self.output is None else repr(self.output)
        if self.how == "conditional":
            options = ", ".join("null" if p is None else repr(p) for p in self.possible)
            return f"at {self.column} = {self.member} f gives one of {options} ({self.because})"
        tail = f"handled in the code: {self.because}" if self.how == "explicit" else f"not handled: {self.because}"
        return f"at {self.column} = {self.member} f gave {given} ({tail})"


class _Evaluation:
    """The rule's expression evaluated with one column a hole."""

    def __init__(self, fn: ast.FunctionDef, names: dict[str, Any], frame: str,
                 column: str, member: str) -> None:
        self.fn = fn
        self.names = names
        self.frame = frame
        self.column = column
        self.member = member
        self.explicit: list[str] = []
        self.nan_ordered = False
        self.null_compared = False

    def _column_of(self, node: ast.AST) -> str | None:
        name = _call_name(node)
        if name in _COL and isinstance(node, ast.Call):
            return _text(node.args[0], self.fn)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                and node.value.id == self.frame:
            return node.attr
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) \
                and node.value.id == self.frame:
            return _text(node.slice, self.fn)
        return None

    def value(self, node: ast.AST) -> Any:
        """A literal, `None` for a null, NaN for a nan hole, or `OTHER`."""
        column = self._column_of(node)
        if column is not None:
            if column != self.column:
                return OTHER
            return None if self.member == "null" else math.nan
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            inner = self.value(node.operand)
            return inner if inner in (None, OTHER) else -inner
        if isinstance(node, ast.Name) and node.id in self.names:
            return self.names[node.id]
        name = _call_name(node)
        if name in _LIT and isinstance(node, ast.Call):
            return self.value(node.args[0])
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left, right = self.value(node.left), self.value(node.right)
            if left is None or right is None:
                return None
            if left is OTHER or right is OTHER:
                return OTHER
            ops = {ast.Add: operator.add, ast.Sub: operator.sub,
                   ast.Mult: operator.mul, ast.Div: operator.truediv}
            return ops[type(node.op)](left, right)
        if name == "coalesce" and isinstance(node, ast.Call):
            for arg in node.args:
                got = self.value(arg)
                if got is None and self._column_of(arg) == self.column:
                    self.explicit.append("coalesce")
                if got is not None:
                    return got
            return None
        raise NotRead(f"a value this translation does not read: {ast.unparse(node)}")

    def compare(self, op: ast.cmpop, a: Any, b: Any) -> str:
        if a is OTHER or b is OTHER:
            return U
        if a is None or b is None:
            self.null_compared = True
            return N
        a_nan = isinstance(a, float) and math.isnan(a)
        b_nan = isinstance(b, float) and math.isnan(b)
        if a_nan or b_nan:
            self.nan_ordered = True
            if isinstance(op, ast.Eq):
                return T if a_nan and b_nan else F
            if isinstance(op, ast.NotEq):
                return F if a_nan and b_nan else T
            above = (a_nan and not b_nan, b_nan and not a_nan)
            if isinstance(op, (ast.Gt, ast.GtE)):
                return T if above[0] or (a_nan and b_nan and isinstance(op, ast.GtE)) else F
            if isinstance(op, (ast.Lt, ast.LtE)):
                return T if above[1] or (a_nan and b_nan and isinstance(op, ast.LtE)) else F
        result = {ast.Lt: a < b, ast.LtE: a <= b, ast.Gt: a > b, ast.GtE: a >= b,
                  ast.Eq: a == b, ast.NotEq: a != b}[type(op)]
        return T if result else F

    def condition(self, node: ast.AST) -> str:
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            return self.compare(node.ops[0], self.value(node.left), self.value(node.comparators[0]))
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.BitAnd, ast.BitOr)):
            left, right = self.condition(node.left), self.condition(node.right)
            if isinstance(node.op, ast.BitAnd):
                if F in (left, right):
                    return F
                if U in (left, right):
                    return U
                return N if N in (left, right) else T
            if T in (left, right):
                return T
            if U in (left, right):
                return U
            return N if N in (left, right) else F
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Invert):
            return {T: F, F: T, N: N, U: U}[self.condition(node.operand)]
        if _call_name(node) == "isnan" and isinstance(node, ast.Call) and len(node.args) == 1:
            got = self.value(node.args[0])
            if self._column_of(node.args[0]) == self.column:
                self.explicit.append("isnan")
            if got is OTHER:
                return U
            return T if isinstance(got, float) and math.isnan(got) else F
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            method, target = node.func.attr, node.func.value
            if method in ("isNull", "isNotNull"):
                got = self.value(target)
                if self._column_of(target) == self.column:
                    self.explicit.append(method)
                if got is OTHER:
                    return U
                is_null = got is None
                return (T if is_null else F) if method == "isNull" else (F if is_null else T)
            if method == "between" and len(node.args) == 2:
                low = ast.Compare(left=target, ops=[ast.GtE()], comparators=[node.args[0]])
                high = ast.Compare(left=target, ops=[ast.LtE()], comparators=[node.args[1]])
                return self.condition(ast.BinOp(left=low, op=ast.BitAnd(), right=high))
            if method == "isin":
                values = node.args[0].elts if len(node.args) == 1 and isinstance(node.args[0], (ast.List, ast.Tuple)) \
                    else node.args
                if not values:
                    return F
                combined: ast.expr = ast.Compare(left=target, ops=[ast.Eq()], comparators=[values[0]])
                for v in values[1:]:
                    combined = ast.BinOp(left=combined, op=ast.BitOr(),
                                         right=ast.Compare(left=target, ops=[ast.Eq()], comparators=[v]))
                return self.condition(combined)
        raise NotRead(f"a condition this translation does not read: {ast.unparse(node)}")


def _chain(node: ast.AST) -> tuple[list[tuple[ast.AST, ast.AST]], ast.AST | None, bool]:
    """`(branches in order, otherwise or None, whether it is a when chain)`."""
    branches: list[tuple[ast.AST, ast.AST]] = []
    otherwise = None
    current = node
    if isinstance(current, ast.Call) and isinstance(current.func, ast.Attribute) \
            and current.func.attr == "otherwise":
        otherwise = current.args[0]
        current = current.func.value
    while isinstance(current, ast.Call) and len(current.args) == 2:
        func = current.func
        if isinstance(func, ast.Attribute) and func.attr == "when" and isinstance(func.value, ast.Call):
            branches.append((current.args[0], current.args[1]))
            current = func.value
            continue
        if _call_name(current) == "when":
            branches.append((current.args[0], current.args[1]))
            return list(reversed(branches)), otherwise, True
        break
    return [], None, False


def _outcome(evaluation: _Evaluation, expression: ast.AST) -> HoleOutcome:
    column, member = evaluation.column, evaluation.member
    branches, otherwise, is_chain = _chain(expression)
    if not is_chain:
        got = evaluation.value(expression)
        if got is OTHER:
            return HoleOutcome(column, member, None, "conditional",
                               "the value depends on another column", ())
        output = None if got is None or (isinstance(got, float) and math.isnan(got)) else got
        if evaluation.explicit:
            return HoleOutcome(column, member, output, "explicit", ", ".join(dict.fromkeys(evaluation.explicit)))
        why = "null passes through the expression" if member == "null" else "NaN passes through the expression"
        return HoleOutcome(column, member, output, "implicit", why)
    possible: list[Any] = []
    for cond, value in branches:
        before = len(evaluation.explicit)
        said = evaluation.condition(cond)
        tested = evaluation.explicit[before:]
        if said in (F, N):
            continue
        got = evaluation.value(value)
        output = OTHER if got is OTHER else None if got is None else got
        if said == U:
            possible.append(output)
            continue
        if possible:
            possible.append(output)
            return HoleOutcome(column, member, None, "conditional",
                               "which branch fires depends on another column",
                               tuple(p for p in possible if p is not OTHER))
        if tested:
            return HoleOutcome(column, member, output if output is not OTHER else None,
                               "explicit", ", ".join(dict.fromkeys(tested)))
        why = "NaN is above every number, so a comparison selected this branch" \
            if evaluation.nan_ordered else "this branch's condition holds at the hole without testing for it"
        return HoleOutcome(column, member, output if output is not OTHER else None, "implicit", why)
    final = None if otherwise is None else evaluation.value(otherwise)
    final = None if final is OTHER and otherwise is None else final
    if possible:
        possible.append(final)
        return HoleOutcome(column, member, None, "conditional",
                           "which branch fires depends on another column",
                           tuple(p for p in possible if p is not OTHER))
    if otherwise is None:
        why = "every condition is false or null there, and there is no otherwise"
    elif evaluation.null_compared:
        why = "every condition is null or false there (a comparison with null is null), so otherwise"
    elif evaluation.nan_ordered:
        why = "every condition is false there (NaN compared as above every number), so otherwise"
    else:
        why = "every condition is false there, so otherwise"
    return HoleOutcome(column, member, None if final is OTHER else final, "implicit", why)


def holes(target: Any, column: str, *, admits: dict[str, set[str]] | None = None,
          float_columns: set[str] | None = None) -> list[HoleOutcome]:
    """What the Spark function `target` (a function or its dotted path)
    writes to `column` at each hole of each input column it reads.
    `admits` maps an input column to the holes it admits; without it,
    every column admits `null`, and `nan` too when it is in
    `float_columns` (every column, when that is not given)."""
    name, _modname, tree = _source(target)
    fn = _function(tree, name)
    frame = fn.args.args[0].arg if fn.args.args else "df"
    set_columns = _columns_set(fn, frame)
    if column not in set_columns:
        raise NotRead(f"{name} sets no column {column!r} with withColumn")
    expression = set_columns[column]
    names = {**_constants(tree), **_defaults(fn)}
    probe = _Evaluation(fn, names, frame, "\0", "null")
    found_at: dict[str, tuple[int, int]] = {}
    for node in ast.walk(expression):
        found = probe._column_of(node)
        if found is not None:
            at = (getattr(node, "lineno", 0), getattr(node, "col_offset", 0))
            found_at[found] = min(found_at.get(found, at), at)
    read = sorted(found_at, key=found_at.__getitem__)
    out: list[HoleOutcome] = []
    for input_column in read:
        if admits is not None:
            members = sorted(admits.get(input_column, set()), key=lambda m: (m != "null", m))
        else:
            floating = float_columns is None or input_column in float_columns
            members = ["null", "nan"] if floating else ["null"]
        for member in members:
            out.append(_outcome(_Evaluation(fn, names, frame, input_column, member), expression))
    return out


__all__ = ["HoleOutcome", "holes"]
