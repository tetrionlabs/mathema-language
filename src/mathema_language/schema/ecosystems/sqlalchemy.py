# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The SQLAlchemy ecosystem: a record is a dict of column values (a
`Table`) or an instance of the declarative class. The neutral checker
holds types and readable bounds; NOT NULL and CHECK are held by
inserting the record into an in-memory SQLite database and rolling
back, so the constraint semantics are the database's. SQLAlchemy is
imported inside the methods that need it, never at module level."""
from __future__ import annotations

import re
from typing import Any

from ..._surface import Problem
from ..checks import row_problems
from ..model import RowSchema

_NOT_NULL = re.compile(r"NOT NULL constraint failed: \w+\.(\w+)")
_CHECK = re.compile(r"CHECK constraint failed: ([^\n]+?)\s*(?:\n|$)")


def _problem_from(message: str, value: Any) -> Problem:
    """The SQLite integrity message as a problem in the path grammar."""
    m = _NOT_NULL.search(message)
    if m:
        return Problem(f".{m.group(1)}", "not null", None)
    m = _CHECK.search(message)
    if m:
        return Problem("", f"check {m.group(1)}", value)
    return Problem("", message.strip(), value)


def _unstorable(values: dict[str, Any]) -> list[Problem]:
    """Text the database cannot store: a lone surrogate has no UTF-8
    encoding, so it is not a member of any text column."""
    out: list[Problem] = []
    for name, value in values.items():
        if isinstance(value, str):
            try:
                value.encode("utf-8")
            except UnicodeEncodeError:
                out.append(Problem(f".{name}", "encodable as UTF-8", value))
    return out


class SqlAlchemyEcosystem:
    """Records of `table`, as dicts or as instances of `cls`."""

    name = "sqlalchemy"

    def __init__(self, table: Any, cls: type | None = None) -> None:
        self.table = table
        self.cls = cls
        self._database: Any = None

    def accepts(self, obj: Any) -> bool:
        return obj is self.table or (self.cls is not None and obj is self.cls)

    def to_model(self, obj: Any) -> RowSchema:
        from ..adaptors.sqlalchemy import _row_schema_of
        return _row_schema_of(obj)

    def build_row(self, schema: RowSchema, values: dict[str, Any]) -> Any:
        return self.cls(**values) if self.cls is not None else dict(values)

    def values(self, row: Any) -> dict[str, Any]:
        if isinstance(row, dict):
            return dict(row)
        return {c.name: getattr(row, c.name, None) for c in self.table.columns}

    def _engine(self) -> Any:
        """An in-memory database holding every table of the metadata,
        made once."""
        if self._database is None:
            import sqlalchemy as sa
            self._database = sa.create_engine("sqlite://")
            self.table.metadata.create_all(self._database)
        return self._database

    def _insert(self, row: dict[str, Any]) -> list[Problem]:
        """Insert `row` in a transaction that is always rolled back; an
        integrity error is the problem."""
        import sqlalchemy as sa
        from sqlalchemy.exc import IntegrityError, StatementError
        with self._engine().connect() as conn:
            trans = conn.begin()
            try:
                conn.execute(sa.insert(self.table), [row])
            except IntegrityError as e:
                return [_problem_from(str(e.orig), row)]
            except StatementError as e:
                return [Problem("", str(e.orig or e).splitlines()[0], row)]
            finally:
                trans.rollback()
        return []

    def validate_row(self, schema: RowSchema, row: Any) -> list[Problem]:
        if self.cls is not None and not isinstance(row, self.cls):
            return [Problem("", f"an instance of {self.cls.__name__}", row)]
        if self.cls is None and not isinstance(row, dict):
            return [Problem("", "a mapping record", row)]
        values = self.values(row)
        neutral = row_problems(schema, values) or _unstorable(values)
        if neutral:
            return neutral
        return self._insert(values)


__all__ = ["SqlAlchemyEcosystem"]
