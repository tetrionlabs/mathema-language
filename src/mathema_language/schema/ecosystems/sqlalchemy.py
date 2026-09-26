# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The SQLAlchemy ecosystem: a record is a dict of column values (a
`Table`) or an instance of the declarative class, a table a list of
them. The neutral checker holds types and readable bounds; NOT NULL,
UNIQUE, CHECK and, when parent rows are supplied, FOREIGN KEY are
held by inserting into an in-memory SQLite database and rolling
back, so the constraint semantics are the database's. SQLAlchemy is
imported inside the methods that need it, never at module level."""
from __future__ import annotations

import re
from typing import Any

from ..._surface import Problem
from ..checks import frame_problems, row_problems
from ..model import RowSchema, TableSchema

_UNIQUE = re.compile(r"UNIQUE constraint failed: (.+)")
_NOT_NULL = re.compile(r"NOT NULL constraint failed: \w+\.(\w+)")
_CHECK = re.compile(r"CHECK constraint failed: (\w+)")


def _problem_from(message: str, value: Any) -> Problem:
    """The SQLite integrity message as a problem in the path grammar."""
    m = _UNIQUE.search(message)
    if m:
        cols = [part.strip().split(".")[-1] for part in m.group(1).split(",")]
        return Problem(f"key({', '.join(cols)})", "unique", value)
    m = _NOT_NULL.search(message)
    if m:
        return Problem(f".{m.group(1)}", "not null", None)
    m = _CHECK.search(message)
    if m:
        return Problem("", f"check {m.group(1)}", value)
    if "FOREIGN KEY constraint failed" in message:
        return Problem("fk", "a key of the parent", value)
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
        self._engines: dict[bool, Any] = {}

    def accepts(self, obj: Any) -> bool:
        return obj is self.table or (self.cls is not None and obj is self.cls)

    def to_model(self, obj: Any) -> RowSchema | TableSchema:
        from ..adaptors.sqlalchemy import table_schema_of
        return table_schema_of(obj)

    def build_row(self, schema: RowSchema, values: dict[str, Any]) -> Any:
        return self.cls(**values) if self.cls is not None else dict(values)

    def build_frame(self, table: TableSchema, columns: dict[str, list[Any]]) -> list[Any]:
        names = list(columns)
        n = len(columns[names[0]]) if names else 0
        return [self.build_row(table.row, {name: columns[name][i] for name in names})
                for i in range(n)]

    def values(self, row: Any) -> dict[str, Any]:
        if isinstance(row, dict):
            return dict(row)
        return {c.name: getattr(row, c.name, None) for c in self.table.columns}

    def _engine_for(self, foreign_keys: bool) -> Any:
        """An in-memory database holding every table of the metadata,
        one with foreign keys enforced (the pragma set on each raw
        connection, since it is ignored inside a transaction) and
        one without."""
        if foreign_keys not in self._engines:
            import sqlalchemy as sa
            engine = sa.create_engine("sqlite://")
            if foreign_keys:
                @sa.event.listens_for(engine, "connect")
                def _enforce(dbapi_connection: Any, _record: Any) -> None:
                    dbapi_connection.execute("PRAGMA foreign_keys=ON")
            self.table.metadata.create_all(engine)
            self._engines[foreign_keys] = engine
        return self._engines[foreign_keys]

    def _insert(self, rows: list[dict[str, Any]], parents: dict[str, Any] | None) -> list[Problem]:
        """Insert `rows` (after any parent rows) in one transaction
        that is always rolled back; the integrity errors are the
        problems."""
        import sqlalchemy as sa
        from sqlalchemy.exc import IntegrityError, StatementError
        engine = self._engine_for(bool(parents))
        problems: list[Problem] = []
        with engine.connect() as conn:
            trans = conn.begin()
            try:
                for name, parent_rows in (parents or {}).items():
                    parent = self.table.metadata.tables.get(name)
                    if parent is not None and parent_rows:
                        conn.execute(sa.insert(parent), [self._plain(p, parent) for p in parent_rows])
                for row in rows:
                    try:
                        conn.execute(sa.insert(self.table), [row])
                    except IntegrityError as e:
                        problems.append(_problem_from(str(e.orig), row))
                        trans.rollback()
                        trans = conn.begin()
                        if parents:
                            for name, parent_rows in parents.items():
                                parent = self.table.metadata.tables.get(name)
                                if parent is not None and parent_rows:
                                    conn.execute(sa.insert(parent),
                                                 [self._plain(p, parent) for p in parent_rows])
                    except StatementError as e:
                        problems.append(Problem("", str(e.orig or e).splitlines()[0], row))
            finally:
                trans.rollback()
        return problems

    @staticmethod
    def _plain(row: Any, table: Any) -> dict[str, Any]:
        if isinstance(row, dict):
            return dict(row)
        return {c.name: getattr(row, c.name, None) for c in table.columns}

    def validate_row(self, schema: RowSchema, row: Any) -> list[Problem]:
        if self.cls is not None and not isinstance(row, self.cls):
            return [Problem("", f"an instance of {self.cls.__name__}", row)]
        if self.cls is None and not isinstance(row, dict):
            return [Problem("", "a mapping record", row)]
        values = self.values(row)
        neutral = row_problems(schema, values) or _unstorable(values)
        if neutral:
            return neutral
        return self._insert([values], None)

    def validate_frame(self, table: TableSchema, frame: Any,
                       parents: dict[str, Any] | None = None) -> list[Problem]:
        if not isinstance(frame, (list, tuple)):
            return [Problem("", "a list of records", frame)]
        rows = list(frame)
        neutral = frame_problems(table, rows, self.column_names(frame),
                                 lambda row: self.validate_row(table.row, row),
                                 lambda row, col: (row.get(col) if isinstance(row, dict)
                                                   else getattr(row, col, None)),
                                 {k: list(v) for k, v in (parents or {}).items()})
        if neutral:
            return neutral
        return self._insert([self.values(r) for r in rows], parents)

    def row_count(self, frame: Any) -> int:
        return len(frame)

    def column_names(self, frame: Any) -> tuple[str, ...] | None:
        if self.cls is not None:
            return tuple(c.name for c in self.table.columns)
        names: list[str] = []
        for row in frame:
            if isinstance(row, dict):
                for k in row:
                    if k not in names:
                        names.append(str(k))
        return tuple(names) if frame else None

    def cell(self, frame: Any, i: int, column: str) -> Any:
        return self.values(frame[i]).get(column)


__all__ = ["SqlAlchemyEcosystem"]
