# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The neutral checker and the JSON Schema rendering of the model.

Problems carry a path in one grammar for every ecosystem: `""` is the
value itself, `.col` a column of a row, `[i]` a row of a table or an
item of a list, `[i].col` a cell, `key(a, b)` a duplicated key,
`fk(col)->parent` an orphan, `rows` the row count, and `order(col)` a
sort violation."""
from __future__ import annotations

import datetime as _dt
import decimal
import math
import re
from collections.abc import Callable, Iterable
from typing import Any

from .._surface import Problem
from .model import NO_DEFAULT, Constraints, Field, NeutralType, RowSchema, TableSchema


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _scalar_problems(value: Any, t: NeutralType, path: str,
                     nan_allowed: bool) -> list[Problem]:
    """Every way `value` fails a scalar type `t`; containers are the
    walker's."""
    base = t.base
    if base == "any":
        return []
    if base == "bool":
        return [] if isinstance(value, bool) else [Problem(path, "bool", value)]
    if base == "int":
        if not _is_int(value):
            return [Problem(path, "int", value)]
        if t.bits:
            lo, hi = ((-(1 << (t.bits - 1)), (1 << (t.bits - 1)) - 1) if t.signed
                      else (0, (1 << t.bits) - 1))
            if not lo <= value <= hi:
                return [Problem(path, t.render(), value)]
        return []
    if base == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return [Problem(path, "float", value)]
        if isinstance(value, float) and math.isnan(value) and not nan_allowed:
            return [Problem(path, "not nan", value)]
        return []
    if base == "decimal":
        return [] if isinstance(value, (decimal.Decimal, int)) and not isinstance(value, bool) \
            else [Problem(path, "decimal", value)]
    if base == "string":
        return [] if isinstance(value, str) else [Problem(path, "string", value)]
    if base == "binary":
        return [] if isinstance(value, (bytes, bytearray)) else [Problem(path, "binary", value)]
    if base == "date":
        return [] if isinstance(value, _dt.date) and not isinstance(value, _dt.datetime) \
            else [Problem(path, "date", value)]
    if base == "time":
        return [] if isinstance(value, _dt.time) else [Problem(path, "time", value)]
    if base == "datetime":
        if not isinstance(value, _dt.datetime):
            return [Problem(path, "datetime", value)]
        if (value.tzinfo is None) != (t.tz is None):
            return [Problem(path, "naive datetime" if t.tz is None else f"datetime in {t.tz}", value)]
        return []
    if base == "duration":
        return [] if isinstance(value, _dt.timedelta) else [Problem(path, "duration", value)]
    if base == "categorical":
        levels = t.levels or ()
        return [] if value in levels else [Problem(path, f"one of {list(levels)}", value)]
    return []


def type_problems(value: Any, t: NeutralType, path: str = "",
                  nan_allowed: bool = False,
                  definitions: RowSchema | None = None) -> list[Problem]:
    """Every way `value` fails to be of type `t`; a `ref` resolves
    through `definitions`, the schema whose record types it names."""
    walker = _Walker(definitions)
    walker.push_type(value, t, path, nan_allowed)
    return walker.run()


class _Walker:
    """One depth-first pass over a value and its schema with an
    explicit stack, so a value nested past the interpreter's recursion
    limit is checked, problems come out in field order, and a container
    met again on its own path is a cycle, reported where it closes."""

    def __init__(self, definitions: RowSchema | None) -> None:
        self.definitions = definitions
        self.stack: list[tuple[Any, ...]] = []
        self.out: list[Problem] = []
        self.on_path: dict[int, str] = {}

    def run(self) -> list[Problem]:
        while self.stack:
            task = self.stack.pop()
            getattr(self, "_" + task[0])(*task[1:])
        return self.out

    def push_type(self, value: Any, t: NeutralType, path: str, nan_allowed: bool = False) -> None:
        self.stack.append(("type", value, t, path, nan_allowed))

    def push_row(self, schema: RowSchema, row: Any, path: str,
                 read: Callable[[Any, str], tuple[bool, Any]] | None = None,
                 columns: Callable[[Any], tuple[str, ...] | None] | None = None,
                 ) -> None:
        self.stack.append(("row", schema, row, path, read or _read, columns or _columns_of))

    def push_field(self, value: Any, f: Field, path: str) -> None:
        self.stack.append(("field", value, f, path))

    def _leave(self, value_id: int) -> None:
        self.on_path.pop(value_id, None)

    def _enter(self, value: Any, path: str) -> bool:
        """Mark a container on the current path; False for a cycle."""
        seen = self.on_path.get(id(value))
        if seen is not None:
            self.out.append(Problem(path, f"acyclic: this is the value at {seen or 'the root'}",
                                    type(value).__name__))
            return False
        self.on_path[id(value)] = path
        self.stack.append(("leave", id(value)))
        return True

    def _constraints(self, value: Any, f: Field, path: str, before: int) -> None:
        if len(self.out) == before:
            self.out.extend(constraint_problems(value, f.constraints, path))

    def _field(self, value: Any, f: Field, path: str) -> None:
        if value is None:
            if not f.nullable:
                self.out.append(Problem(path, "not null", value))
            return
        self.stack.append(("constraints", value, f, path, len(self.out)))
        self.push_type(value, f.type, path, f.nan_allowed)

    def _type(self, value: Any, t: NeutralType, path: str, nan_allowed: bool) -> None:
        base = t.base
        if base == "list":
            if not isinstance(value, (list, tuple)):
                self.out.append(Problem(path, "list", value))
                return
            if t.item is None or not self._enter(value, path):
                return
            for i in range(len(value) - 1, -1, -1):
                self.push_type(value[i], t.item, f"{path}[{i}]")
            return
        if base == "map":
            if not isinstance(value, dict):
                self.out.append(Problem(path, "map", value))
                return
            if not self._enter(value, path):
                return
            for k, v in reversed(list(value.items())):
                if t.value is not None:
                    self.push_type(v, t.value, f"{path}[{k!r}]")
                if t.key is not None:
                    self.push_type(k, t.key, f"{path}[{k!r}]")
            return
        if base == "struct":
            if t.fields is None:
                return
            self.push_row(RowSchema("struct", t.fields), value, path)
            return
        if base == "ref":
            if self.definitions is None or t.ref is None:
                return
            try:
                schema = self.definitions.definition(t.ref)
            except KeyError:
                self.out.append(Problem(path, f"a definition named {t.ref}", value))
                return
            self.push_row(schema, value, path)
            return
        self.out.extend(_scalar_problems(value, t, path, nan_allowed))

    def _row(self, schema: RowSchema, row: Any, path: str,
             read: Callable[[Any, str], tuple[bool, Any]],
             columns: Callable[[Any], tuple[str, ...] | None]) -> None:
        if (not isinstance(row, (dict, list, tuple, set)) and not hasattr(row, "__dict__")
                and not hasattr(row, "__slots__")
                and not any(read(row, f.name)[0] for f in schema.fields)):
            self.out.append(Problem(path, schema.name, row))
            return
        if not self._enter(row, path):
            return
        if schema.column_policy == "exact":
            self.stack.append(("extras", schema, row, path, columns))
        for f in reversed(schema.fields):
            present, value = read(row, f.name)
            if not present:
                if f.required and f.default is NO_DEFAULT:
                    self.stack.append(("missing", f"{path}.{f.name}"))
                continue
            self.push_field(value, f, f"{path}.{f.name}")

    def _missing(self, path: str) -> None:
        self.out.append(Problem(path, "present", None))

    def _extras(self, schema: RowSchema, row: Any, path: str,
                columns: Callable[[Any], tuple[str, ...] | None]) -> None:
        names = columns(row)
        if names is not None:
            for extra in names:
                if extra not in schema.names:
                    self.out.append(Problem(f"{path}.{extra}", "a column of the schema", None))


def constraint_problems(value: Any, c: Constraints, path: str = "") -> list[Problem]:
    """Every constraint in `c` that `value` breaks."""
    out: list[Problem] = []
    try:
        if c.min is not None and value < c.min:
            out.append(Problem(path, f">= {c.min}", value))
        if c.max is not None and value > c.max:
            out.append(Problem(path, f"<= {c.max}", value))
        if c.exclusive_min is not None and value <= c.exclusive_min:
            out.append(Problem(path, f"> {c.exclusive_min}", value))
        if c.exclusive_max is not None and value >= c.exclusive_max:
            out.append(Problem(path, f"< {c.exclusive_max}", value))
    except TypeError:
        out.append(Problem(path, "comparable to its bounds", value))
    if c.min_len is not None or c.max_len is not None:
        try:
            n = len(value)
        except TypeError:
            out.append(Problem(path, "sized", value))
        else:
            if c.min_len is not None and n < c.min_len:
                out.append(Problem(path, f"len >= {c.min_len}", value))
            if c.max_len is not None and n > c.max_len:
                out.append(Problem(path, f"len <= {c.max_len}", value))
    if c.regex is not None and isinstance(value, str) and re.fullmatch(c.regex, value) is None:
        out.append(Problem(path, f"matches {c.regex!r}", value))
    if c.enum is not None and value not in c.enum:
        out.append(Problem(path, f"one of {list(c.enum)}", value))
    if c.const is not NO_DEFAULT and value != c.const:
        out.append(Problem(path, f"== {c.const!r}", value))
    if c.multiple_of is not None:
        try:
            if value % c.multiple_of != 0:
                out.append(Problem(path, f"multiple of {c.multiple_of}", value))
        except (TypeError, ZeroDivisionError):
            out.append(Problem(path, f"multiple of {c.multiple_of}", value))
    return out


def field_problems(value: Any, f: Field, path: str = "",
                   definitions: RowSchema | None = None) -> list[Problem]:
    """Every way `value` fails field `f`: null where none is allowed,
    the type, then the constraints."""
    walker = _Walker(definitions)
    walker.push_field(value, f, path)
    return walker.run()


def _read(row: Any, name: str) -> tuple[bool, Any]:
    """`(present, value)` for a column of a mapping or an attribute row."""
    if isinstance(row, dict):
        return (name in row, row.get(name))
    if hasattr(row, name):
        return (True, getattr(row, name))
    return (False, None)


def _columns_of(row: Any) -> tuple[str, ...] | None:
    """The column names a row carries, or None when they cannot be
    read (an attribute row's extras are not observable)."""
    if isinstance(row, dict):
        return tuple(str(k) for k in row)
    return None


def row_problems(schema: RowSchema, row: Any, path: str = "",
                 read: Callable[[Any, str], tuple[bool, Any]] = _read,
                 columns: Callable[[Any], tuple[str, ...] | None] = _columns_of,
                 definitions: RowSchema | None = None) -> list[Problem]:
    """Every way `row` fails `schema`: a missing required column, an
    extra column under the exact policy, and each field's problems
    at `path.col`, at any depth; a `ref` resolves through `definitions`
    (the schema itself by default)."""
    walker = _Walker(definitions if definitions is not None else schema)
    walker.push_row(schema, row, path, read, columns)
    return walker.run()


def check_problems(checks: Iterable[Callable[[Any], bool]], value: Any, path: str = "") -> list[Problem]:
    """Every opaque check that refuses `value`, a raising check
    counting as a refusal."""
    out: list[Problem] = []
    for check in checks:
        try:
            ok = bool(check(value))
        except Exception:
            ok = False
        if not ok:
            out.append(Problem(path, f"check {getattr(check, '__name__', repr(check))}", value))
    return out


def frame_problems(table: TableSchema, rows: list[Any], columns: tuple[str, ...] | None,
                   row_check: Callable[[Any], list[Problem]],
                   cell: Callable[[Any, str], Any],
                   parents: dict[str, list[Any]] | None = None) -> list[Problem]:
    """Every way a table fails `table`: the row count, each row's
    problems at `[i]`, a duplicated key at `key(a, b)`, an orphan at
    `fk(col)->parent` when the parent table is given, a missing or
    extra column, and a sort violation at `order(col)`."""
    out: list[Problem] = []
    lo, hi = table.row_count
    n = len(rows)
    if n < lo:
        out.append(Problem("rows", f">= {lo}", n))
    if hi is not None and n > hi:
        out.append(Problem("rows", f"<= {hi}", n))
    if columns is not None:
        for name in table.row.names:
            if name not in columns and table.row.field(name).required:
                out.append(Problem(f".{name}", "present", None))
        if table.row.column_policy == "exact":
            for extra in columns:
                if extra not in table.row.names:
                    out.append(Problem(f".{extra}", "a column of the schema", None))
    for i, row in enumerate(rows):
        for problem in row_check(row):
            out.append(Problem(f"[{i}]{problem.path}", problem.predicate, problem.value))
    for cols in table.key_sets:
        seen: dict[tuple[Any, ...], int] = {}
        for i, row in enumerate(rows):
            key = tuple(_hashable(cell(row, c)) for c in cols)
            if key in seen:
                out.append(Problem(f"key({', '.join(cols)})", "unique", key))
            else:
                seen[key] = i
    for f in table.row.fields:
        if f.unique and (f.name,) not in table.key_sets:
            seen_values: set[Any] = set()
            for row in rows:
                v = _hashable(cell(row, f.name))
                if v in seen_values:
                    out.append(Problem(f"key({f.name})", "unique", v))
                seen_values.add(v)
    if parents:
        for fk in table.foreign_keys:
            parent_rows = parents.get(fk.parent)
            if parent_rows is None:
                continue
            keys = {tuple(_hashable(cell(p, c)) for c in fk.parent_columns) for p in parent_rows}
            for row in rows:
                key = tuple(_hashable(cell(row, c)) for c in fk.columns)
                if key not in keys:
                    out.append(Problem(f"fk({', '.join(fk.columns)})->{fk.parent}", "a key of the parent", key))
    for col in table.ordered:
        values = [cell(row, col) for row in rows]
        try:
            if values != sorted(values):
                out.append(Problem(f"order({col})", "sorted", None))
        except TypeError:
            out.append(Problem(f"order({col})", "sortable", None))
    out.extend(check_problems(table.checks, rows))
    return out


def _hashable(value: Any) -> Any:
    try:
        hash(value)
        return value
    except TypeError:
        return repr(value)


def json_schema(obj: NeutralType | Field | RowSchema | TableSchema) -> dict[str, Any]:
    """The JSON Schema (draft 2020-12) of a type, a field, a row or a
    table; ecosystem detail that JSON Schema cannot say (a fixed
    width, a time zone, keys) rides in `x-mathema`."""
    if isinstance(obj, TableSchema):
        out: dict[str, Any] = {"type": "array", "items": json_schema(obj.row)}
        lo, hi = obj.row_count
        if lo:
            out["minItems"] = lo
        if hi is not None:
            out["maxItems"] = hi
        extra: dict[str, Any] = {}
        if obj.primary_key:
            extra["primary_key"] = list(obj.primary_key)
        if obj.unique:
            extra["unique"] = [list(u) for u in obj.unique]
        if obj.foreign_keys:
            extra["foreign_keys"] = [{"columns": list(fk.columns), "parent": fk.parent,
                                      "parent_columns": list(fk.parent_columns)}
                                     for fk in obj.foreign_keys]
        if obj.ordered:
            extra["ordered"] = list(obj.ordered)
        if extra:
            out["x-mathema"] = extra
        return out
    if isinstance(obj, RowSchema):
        properties = {f.name: json_schema(f) for f in obj.fields}
        definitions = {name: json_schema(RowSchema(d.name, d.fields, d.column_policy))
                       for name, d in obj.definitions}
        required = [f.name for f in obj.fields if f.required and f.default is NO_DEFAULT]
        out = {"type": "object", "title": obj.name, "properties": properties}
        if required:
            out["required"] = required
        if obj.column_policy == "exact":
            out["additionalProperties"] = False
        if definitions:
            out["$defs"] = definitions
        return out
    if isinstance(obj, Field):
        out = json_schema(obj.type)
        if obj.nullable:
            out = {"anyOf": [out, {"type": "null"}]}
        c = obj.constraints
        for key, value in (("minimum", c.min), ("maximum", c.max),
                           ("exclusiveMinimum", c.exclusive_min),
                           ("exclusiveMaximum", c.exclusive_max),
                           ("multipleOf", c.multiple_of), ("pattern", c.regex)):
            if value is not None:
                out[key] = value
        if c.min_len is not None:
            out["minLength" if obj.type.base in ("string", "binary") else "minItems"] = c.min_len
        if c.max_len is not None:
            out["maxLength" if obj.type.base in ("string", "binary") else "maxItems"] = c.max_len
        if c.enum is not None:
            out["enum"] = list(c.enum)
        if c.const is not NO_DEFAULT:
            out["const"] = c.const
        if obj.default is not NO_DEFAULT:
            out["default"] = obj.default
        if obj.unique:
            out.setdefault("x-mathema", {})["unique"] = True
        if obj.nan_allowed:
            out.setdefault("x-mathema", {})["nan_allowed"] = True
        return out
    t = obj
    base = t.base
    if base == "bool":
        return {"type": "boolean"}
    if base == "int":
        out = {"type": "integer"}
        if t.bits:
            out["x-mathema"] = {"bits": t.bits, "signed": t.signed}
        return out
    if base in ("float", "decimal"):
        out = {"type": "number"}
        if base == "decimal":
            out["x-mathema"] = {"decimal": True, "precision": t.precision, "scale": t.scale}
        return out
    if base == "string":
        return {"type": "string"}
    if base == "binary":
        return {"type": "string", "contentEncoding": "base64"}
    if base in ("date", "time", "datetime", "duration"):
        out = {"type": "string", "format": {"date": "date", "time": "time",
                                            "datetime": "date-time", "duration": "duration"}[base]}
        if t.tz or t.unit:
            out["x-mathema"] = {k: v for k, v in (("tz", t.tz), ("unit", t.unit)) if v}
        return out
    if base == "categorical":
        return {"enum": list(t.levels or ())}
    if base == "ref":
        return {"$ref": f"#/$defs/{t.ref}"}
    if base == "list":
        return {"type": "array", "items": json_schema(t.item) if t.item else {}}
    if base == "struct":
        return json_schema(RowSchema("struct", t.fields or ()))
    if base == "map":
        return {"type": "object", "additionalProperties": json_schema(t.value) if t.value else {}}
    return {}


__all__ = ["check_problems", "constraint_problems", "field_problems", "frame_problems",
           "json_schema", "row_problems", "type_problems"]
