# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A column a Spark function computes, lowered to a plain Python
function of the columns it reads. The function's source is read, never
imported or run, so pyspark need not be installed: its `withColumn`
chain is found, the column's expression is translated, and the result
is a function with one parameter per column read (each may be `None`,
as a Spark column may be null) that returns what Spark would put in the
column for that row.

Spark's semantics are written into the translation. A comparison with
null is null, and a `when` whose condition is null is skipped, as is one
whose condition is false; a missing `otherwise` gives null. NaN equals
NaN and is greater than every other number. Arithmetic with null is
null. Anything outside the subset read here (a cast, a UDF, a window) is
refused, naming the construct, rather than guessed at."""
from __future__ import annotations

import ast
import importlib.util
import inspect
import itertools
import keyword
import linecache
import math
import textwrap
from collections.abc import Callable
from typing import Any, Optional

#: the column functions read here, by the name they are called with
_COL = {"col", "column"}
_LIT = {"lit"}


class NotRead(ValueError):
    """A construct outside the subset this module translates."""


def _source(target: Any) -> tuple[str, str, ast.Module]:
    """`(function name, module name, module syntax tree)` for a function
    object or a dotted path `pkg.mod.fn`, read from the module's file
    without executing it."""
    if callable(target):
        module = inspect.getmodule(target)
        if module is None or getattr(module, "__file__", None) is None:
            raise NotRead(f"the source of {target!r} cannot be read")
        path, name, modname = str(module.__file__), target.__name__, module.__name__
    else:
        modname, _, name = str(target).rpartition(".")
        spec = importlib.util.find_spec(modname)
        if spec is None or spec.origin is None:
            raise NotRead(f"no module {modname!r} to read {target!r} from")
        path = str(spec.origin)
    with open(path, encoding="utf-8") as handle:
        return name, modname, ast.parse(handle.read(), filename=path)


def _constants(tree: ast.Module) -> dict[str, Any]:
    """Module-level names bound to a literal (`THRESHOLD = 1000`)."""
    out: dict[str, Any] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                continue
    return out


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise NotRead(f"no function {name!r} at the top level of its module")


def _defaults(fn: ast.FunctionDef) -> dict[str, Any]:
    """Each parameter's literal default (`value_col: str = "po_value"`)."""
    args = fn.args.args
    out: dict[str, Any] = {}
    for arg, default in zip(args[len(args) - len(fn.args.defaults):], fn.args.defaults, strict=True):
        try:
            out[arg.arg] = ast.literal_eval(default)
        except ValueError:
            continue
    for arg, kw_default in zip(fn.args.kwonlyargs, fn.args.kw_defaults, strict=True):
        if kw_default is not None:
            try:
                out[arg.arg] = ast.literal_eval(kw_default)
            except ValueError:
                continue
    return out


def _call_name(node: ast.AST) -> str | None:
    """`when` for `when(...)` and `F.when(...)`; None for anything else."""
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            return func.attr
    return None


def _columns_set(fn: ast.FunctionDef, frame: str) -> dict[str, ast.AST]:
    """Every column the function sets with `withColumn`, in the order it
    sets them, through a chain (`df.withColumn(a, x).withColumn(b, y)`)
    or one statement after another (`df = df.withColumn(a, x)`)."""
    out: dict[str, ast.AST] = {}

    def chain(node: ast.AST) -> None:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "withColumn":
            chain(node.func.value)
            if len(node.args) != 2:
                raise NotRead("withColumn with other than two arguments")
            out[_text(node.args[0], fn)] = node.args[1]

    for stmt in ast.walk(fn):
        if isinstance(stmt, (ast.Return, ast.Assign)) and stmt.value is not None:
            chain(stmt.value)
    return out


def _text(node: ast.AST, fn: ast.FunctionDef) -> str:
    """A column name written as a literal or as a parameter with a
    literal default."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and node.id in _defaults(fn):
        value = _defaults(fn)[node.id]
        if isinstance(value, str):
            return value
    raise NotRead(f"a column name that is not a literal: {ast.unparse(node)}")


class _Lowering:
    """The translation of one column's expression into Python source."""

    def __init__(self, fn: ast.FunctionDef, constants: dict[str, Any],
                 set_columns: dict[str, ast.AST], float_columns: set[str] | None) -> None:
        self.fn = fn
        self.frame = fn.args.args[0].arg if fn.args.args else "df"
        self.names = {**constants, **_defaults(fn)}
        self.set_columns = set_columns
        self.float_columns = float_columns
        self.read: dict[str, str] = {}
        #: the Python type each parameter is compared as, from the literals
        self.kinds: dict[str, str] = {}

    # ---- values: (code assuming its columns are not null, the columns read)

    def column(self, name: str) -> tuple[str, frozenset[str]]:
        if name in self.set_columns:
            raise NotRead(f"a column the function itself computes ({name!r}) read by another")
        if name not in self.read:
            plain = name.isidentifier() and not keyword.iskeyword(name) \
                and name not in self.read.values() and name != "Optional"
            self.read[name] = name if plain else f"c{len(self.read)}"
        var = self.read[name]
        return var, frozenset({var})

    def _kind(self, cols: frozenset[str], other: ast.AST) -> None:
        """Note the Python type a lone column is compared as."""
        if len(cols) != 1 or not isinstance(other, ast.Constant):
            return
        (var,) = cols
        value = other.value
        kind = "bool" if isinstance(value, bool) else "float" if isinstance(value, (int, float)) \
            else "str" if isinstance(value, str) else None
        if kind is not None:
            self.kinds.setdefault(var, kind)

    def literal(self, value: Any) -> tuple[str, frozenset[str]]:
        if value is None:
            return "None", frozenset()
        if isinstance(value, float) and math.isnan(value):
            return "float('nan')", frozenset()
        return repr(value), frozenset()

    def value(self, node: ast.AST) -> tuple[str, frozenset[str]]:
        name = _call_name(node)
        if isinstance(node, ast.Constant):
            return self.literal(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            code, cols = self.value(node.operand)
            return f"(-{code})", cols
        if isinstance(node, ast.Name):
            if node.id in self.names:
                return self.literal(self.names[node.id])
            raise NotRead(f"a name with no literal value: {node.id}")
        if name in _COL and isinstance(node, ast.Call):
            return self.column(_text(node.args[0], self.fn))
        if name in _LIT and isinstance(node, ast.Call):
            return self.value(node.args[0])
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                and node.value.id == self.frame:
            return self.column(node.attr)
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) \
                and node.value.id == self.frame:
            return self.column(_text(node.slice, self.fn))
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left, lcols = self.value(node.left)
            right, rcols = self.value(node.right)
            op = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/"}[type(node.op)]
            return f"({left} {op} {right})", lcols | rcols
        raise NotRead(f"a value this translation does not read: {ast.unparse(node)}")

    # ---- conditions: (code true exactly when Spark's condition is true,
    #      code true exactly when it is false); null is neither

    def _nan_aware(self, cols: frozenset[str]) -> bool:
        if self.float_columns is None:
            return bool(cols)
        names = {var: name for name, var in self.read.items()}
        return any(names.get(c) in self.float_columns for c in cols)

    def compare(self, op: ast.cmpop, left: ast.AST, right: ast.AST) -> tuple[str, str]:
        a, acols = self.value(left)
        b, bcols = self.value(right)
        self._kind(acols, right)
        self._kind(bcols, left)
        present =" and ".join(f"{c} is not None" for c in sorted(acols | bcols)) or "True"
        if a == "None" or b == "None":
            return "False", "False"
        nan = self._nan_aware(acols | bcols)
        if isinstance(op, ast.Lt):
            true = f"(({a}) == ({a}) and (({b}) != ({b}) or ({a}) < ({b})))" if nan else f"({a}) < ({b})"
        elif isinstance(op, ast.LtE):
            true = f"(({b}) != ({b}) or (({a}) == ({a}) and ({a}) <= ({b})))" if nan else f"({a}) <= ({b})"
        elif isinstance(op, ast.Gt):
            return self.compare(ast.Lt(), right, left)
        elif isinstance(op, ast.GtE):
            return self.compare(ast.LtE(), right, left)
        elif isinstance(op, ast.Eq):
            true = f"((({a}) != ({a}) and ({b}) != ({b})) or ({a}) == ({b}))" if nan else f"({a}) == ({b})"
        elif isinstance(op, ast.NotEq):
            t, f = self.compare(ast.Eq(), left, right)
            return f, t
        else:
            raise NotRead(f"a comparison this translation does not read: {type(op).__name__}")
        return f"({present} and {true})", f"({present} and not {true})"

    def condition(self, node: ast.AST) -> tuple[str, str]:
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            return self.compare(node.ops[0], node.left, node.comparators[0])
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.BitAnd, ast.BitOr)):
            lt, lf = self.condition(node.left)
            rt, rf = self.condition(node.right)
            if isinstance(node.op, ast.BitAnd):
                return f"({lt} and {rt})", f"({lf} or {rf})"
            return f"({lt} or {rt})", f"({lf} and {rf})"
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Invert):
            t, f = self.condition(node.operand)
            return f, t
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            method = node.func.attr
            target = node.func.value
            if method in ("isNull", "isNotNull"):
                code, cols = self.value(target)
                null = " or ".join(f"{c} is None" for c in sorted(cols)) or f"{code} is None"
                return (f"({null})", f"(not ({null}))") if method == "isNull" \
                    else (f"(not ({null}))", f"({null})")
            if method == "between" and len(node.args) == 2:
                low = ast.Compare(left=target, ops=[ast.GtE()], comparators=[node.args[0]])
                high = ast.Compare(left=target, ops=[ast.LtE()], comparators=[node.args[1]])
                return self.condition(ast.BinOp(left=low, op=ast.BitAnd(), right=high))
            if method == "isin":
                values = node.args[0].elts if len(node.args) == 1 and isinstance(node.args[0], (ast.List, ast.Tuple)) \
                    else node.args
                if not values:
                    return "False", "False"
                parts = [ast.Compare(left=target, ops=[ast.Eq()], comparators=[v]) for v in values]
                combined: ast.expr = parts[0]
                for part in parts[1:]:
                    combined = ast.BinOp(left=combined, op=ast.BitOr(), right=part)
                return self.condition(combined)
        raise NotRead(f"a condition this translation does not read: {ast.unparse(node)}")

    # ---- the column: a chain of whens, a coalesce, or a plain value

    def column_body(self, node: ast.AST, indent: str = "    ") -> list[str]:
        branches: list[tuple[ast.AST, ast.AST]] = []
        otherwise: ast.AST | None = None
        current = node
        if isinstance(current, ast.Call) and isinstance(current.func, ast.Attribute) \
                and current.func.attr == "otherwise":
            otherwise = current.args[0]
            current = current.func.value
        started = False
        while isinstance(current, ast.Call) and len(current.args) == 2:
            func = current.func
            if isinstance(func, ast.Attribute) and func.attr == "when" \
                    and isinstance(func.value, ast.Call):
                branches.append((current.args[0], current.args[1]))
                current = func.value
                continue
            if _call_name(current) == "when":
                branches.append((current.args[0], current.args[1]))
                started = True
            break
        if not started:
            if _call_name(node) == "coalesce" and isinstance(node, ast.Call):
                lines = []
                for arg in node.args:
                    code, cols = self.value(arg)
                    present = " and ".join(f"{c} is not None" for c in sorted(cols)) or "True"
                    lines.append(f"{indent}if {present}:\n{indent}    return {code}")
                return lines + [f"{indent}return None"]
            code, cols = self.value(node)
            absent = " or ".join(f"{c} is None" for c in sorted(cols))
            return ([f"{indent}if {absent}:\n{indent}    return None"] if absent else []) + \
                [f"{indent}return {code}"]
        lines = []
        for cond, value in reversed(branches):
            true, _ = self.condition(cond)
            code, cols = self.value(value)
            result = code if not cols else \
                f"None if ({' or '.join(f'{c} is None' for c in sorted(cols))}) else {code}"
            lines.append(f"{indent}if {true}:\n{indent}    return {result}")
        if otherwise is None:
            lines.append(f"{indent}return None")
        else:
            code, cols = self.value(otherwise)
            result = code if not cols else \
                f"None if ({' or '.join(f'{c} is None' for c in sorted(cols))}) else {code}"
            lines.append(f"{indent}return {result}")
        return lines


_COUNTER = itertools.count()


def rule(target: Callable[..., Any] | str, column: str, *,
         float_columns: set[str] | None = None) -> Callable[..., Any]:
    """The function that computes `column` as the Spark function
    `target` (a function, or its dotted path) computes it, with one
    parameter per input column, in the order they are first read. The
    returned function's `source` attribute holds its Python source, and
    `columns` maps each parameter to the column it stands for.
    `float_columns` names the columns that may hold NaN; without it
    every column read is treated as one that may."""
    name, modname, tree = _source(target)
    fn = _function(tree, name)
    set_columns = _columns_set(fn, fn.args.args[0].arg if fn.args.args else "df")
    if column not in set_columns:
        raise NotRead(f"{modname}.{name} sets no column {column!r} with withColumn")
    expression = set_columns.pop(column)
    lowering = _Lowering(fn, _constants(tree), set_columns, float_columns)
    body = lowering.column_body(expression)
    func_name = f"{name}__{column}".replace("-", "_").replace(" ", "_")
    params = ", ".join(f"{var}: Optional[{lowering.kinds[var]}]" if var in lowering.kinds else var
                       for var in lowering.read.values())
    doc = f'    """The {column!r} column {modname}.{name} computes, from the columns it reads."""\n'
    source = f"def {func_name}({params}):\n" + doc + "\n".join(body) + "\n"
    filename = f"<mathema-lowered {modname}.{name}:{column} #{next(_COUNTER)}>"
    linecache.cache[filename] = (len(source), None, source.splitlines(True), filename)
    namespace: dict[str, Any] = {"__name__": f"mathema_language.lowered.{modname}",
                                 "Optional": Optional}
    exec(compile(source, filename, "exec"), namespace)  # noqa: S102
    lowered = namespace[func_name]
    lowered.source = textwrap.dedent(source)
    lowered.columns = {var: col for col, var in lowering.read.items()}
    return lowered  # type: ignore[no-any-return]


__all__ = ["NotRead", "rule"]
