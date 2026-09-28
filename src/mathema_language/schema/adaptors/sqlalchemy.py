# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A SQLAlchemy `Table`, or a declarative class, as a row schema:
column types, NOT NULL, UNIQUE, the primary key, foreign keys and the
bounds a CHECK constraint spells in plain comparisons, read off the
metadata; membership through an in-memory SQLite database."""
from __future__ import annotations

import re
import sys
from typing import Any

from ..._priority import LIBRARY, priority
from ..ecosystems.sqlalchemy import SqlAlchemyEcosystem
from ..languages import RowLanguage
from ..model import Constraints, Field, ForeignKey, NeutralType, RowSchema, TableSchema

_BETWEEN = re.compile(r"(\w+)\s+BETWEEN\s+(-?\d+(?:\.\d+)?)\s+AND\s+(-?\d+(?:\.\d+)?)", re.I)
_COMPARE = re.compile(r"(\w+)\s*(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)")


def _sa() -> Any:
    return sys.modules.get("sqlalchemy")


def _table_of(obj: Any) -> tuple[Any, type | None] | None:
    """`(table, class)` for a `Table` or a declarative class, decided
    without importing SQLAlchemy."""
    sa = _sa()
    if sa is None:
        return None
    if isinstance(obj, sa.Table):
        return obj, None
    table = getattr(obj, "__table__", None)
    if isinstance(obj, type) and isinstance(table, sa.Table):
        return table, obj
    return None


def _number(text: str) -> float | int:
    return float(text) if "." in text else int(text)


def _check_bounds(table: Any) -> dict[str, dict[str, Any]]:
    """Per column, the bounds its CHECK constraints spell as plain
    comparisons or BETWEEN, whether written on the table or on the
    column itself; anything else is left to the database."""
    sa = _sa()
    out: dict[str, dict[str, Any]] = {}
    on_columns = [c for col in table.columns for c in col.constraints]
    for constraint in [*table.constraints, *on_columns]:
        if not isinstance(constraint, sa.CheckConstraint):
            continue
        text = str(constraint.sqltext)
        for m in _BETWEEN.finditer(text):
            out.setdefault(m.group(1), {}).update(min=_number(m.group(2)), max=_number(m.group(3)))
        text = _BETWEEN.sub("", text)
        for m in _COMPARE.finditer(text):
            col, op, num = m.group(1), m.group(2), _number(m.group(3))
            key = {">=": "min", "<=": "max", ">": "exclusive_min", "<": "exclusive_max"}[op]
            out.setdefault(col, {})[key] = num
    return out


def _type_of(col_type: Any) -> tuple[NeutralType, dict[str, Any]]:
    """`(neutral type, constraint keywords)` of a column type."""
    sa = _sa()
    t = col_type
    if isinstance(t, sa.Boolean):
        return NeutralType("bool"), {}
    if isinstance(t, sa.SmallInteger):
        return NeutralType("int", bits=16), {}
    if isinstance(t, sa.BigInteger):
        return NeutralType("int", bits=64), {}
    if isinstance(t, sa.Integer):
        return NeutralType("int", bits=32), {}
    if isinstance(t, sa.Numeric) and not isinstance(t, sa.Float):
        return NeutralType("decimal", precision=t.precision, scale=t.scale), {}
    if isinstance(t, sa.Float):
        return NeutralType("float"), {}
    if isinstance(t, sa.Enum):
        return NeutralType("categorical", levels=tuple(t.enums)), {}
    if isinstance(t, sa.DateTime):
        return NeutralType("datetime", tz="UTC" if t.timezone else None), {}
    if isinstance(t, sa.Date):
        return NeutralType("date"), {}
    if isinstance(t, sa.Time):
        return NeutralType("time"), {}
    if isinstance(t, sa.Interval):
        return NeutralType("duration"), {}
    if isinstance(t, sa.LargeBinary):
        return NeutralType("binary"), {}
    if isinstance(t, sa.String):
        return NeutralType("string"), ({"max_len": t.length} if t.length else {})
    return NeutralType("any"), {}


def _table_schema_of(obj: Any) -> TableSchema:
    """The table schema of a `Table` or a declarative class."""
    found = _table_of(obj)
    if found is None:
        raise TypeError(f"not a SQLAlchemy table or declarative class: {obj!r}")
    table, _ = found
    sa = _sa()
    bounds = _check_bounds(table)
    fields: list[Field] = []
    for col in table.columns:
        t, extra = _type_of(col.type)
        extra.update(bounds.get(col.name, {}))
        auto = bool(col.primary_key and col.autoincrement in (True, "auto") and t.base == "int")
        has_default = col.default is not None or col.server_default is not None
        # an autoincrement key left None is one the database assigns on insert
        fields.append(Field(col.name, t, nullable=(bool(col.nullable) and not col.primary_key) or auto,
                            required=not (auto or has_default or col.nullable),
                            unique=bool(col.unique), constraints=Constraints(**extra)))
    unique = tuple(tuple(c.name for c in constraint.columns)
                   for constraint in table.constraints
                   if isinstance(constraint, sa.UniqueConstraint))
    foreign = tuple(ForeignKey(tuple(c.name for c in fk.columns), fk.referred_table.name,
                               tuple(e.column.name for e in fk.elements))
                    for fk in table.foreign_key_constraints)
    row = RowSchema(getattr(obj, "__name__", None) or table.name, tuple(fields))
    return TableSchema(row, primary_key=tuple(c.name for c in table.primary_key.columns),
                       unique=unique, foreign_keys=foreign)


@priority(LIBRARY)
def adapt(obj: Any) -> RowLanguage | None:
    """The row language of a `Table` or a declarative class, or None
    for anything else."""
    found = _table_of(obj)
    if found is None:
        return None
    table, cls = found
    schema = _table_schema_of(obj)
    language = RowLanguage(schema.row, SqlAlchemyEcosystem(table, cls))
    language._table_defaults = schema
    return language


__all__ = ["adapt"]
