# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The standard-library ecosystems, the reference every other one is
tested against: `PlainEcosystem` (a record is a dict, a table a list
of them) and `AttributeEcosystem` (a record is an instance of a class
built by keyword, a table a list of them). Both validate with the
neutral checker."""
from __future__ import annotations

import dataclasses
from typing import Any

from ..._surface import Problem
from ..checks import frame_problems, row_problems
from ..model import RowSchema, TableSchema


def _rows(frame: Any) -> list[Any]:
    if isinstance(frame, (list, tuple)):
        return list(frame)
    raise TypeError("a table is a list of records")


class PlainEcosystem:
    """Records are mappings, tables are lists of them."""

    name = "plain"

    def accepts(self, obj: Any) -> bool:
        return isinstance(obj, (RowSchema, TableSchema))

    def to_model(self, obj: Any) -> RowSchema | TableSchema:
        if not self.accepts(obj):
            raise TypeError(f"not a neutral schema: {obj!r}")
        return obj  # type: ignore[no-any-return]

    def build_row(self, schema: RowSchema, values: dict[str, Any]) -> dict[str, Any]:
        return dict(values)

    def build_frame(self, table: TableSchema, columns: dict[str, list[Any]]) -> list[dict[str, Any]]:
        names = list(columns)
        n = len(columns[names[0]]) if names else 0
        return [{name: columns[name][i] for name in names} for i in range(n)]

    def validate_row(self, schema: RowSchema, row: Any) -> list[Problem]:
        if not isinstance(row, dict):
            return [Problem("", "a mapping record", row)]
        return row_problems(schema, row)

    def validate_frame(self, table: TableSchema, frame: Any,
                       parents: dict[str, Any] | None = None) -> list[Problem]:
        try:
            rows = _rows(frame)
        except TypeError:
            return [Problem("", "a list of records", frame)]
        columns = self.column_names(frame)
        return frame_problems(table, rows, columns,
                              lambda row: self.validate_row(table.row, row),
                              lambda row, col: row.get(col) if isinstance(row, dict) else None,
                              {k: _rows(v) for k, v in (parents or {}).items()})

    def row_count(self, frame: Any) -> int:
        return len(_rows(frame))

    def column_names(self, frame: Any) -> tuple[str, ...] | None:
        rows = _rows(frame)
        names: list[str] = []
        for row in rows:
            if isinstance(row, dict):
                for k in row:
                    if k not in names:
                        names.append(str(k))
        return tuple(names) if rows else None

    def cell(self, frame: Any, i: int, column: str) -> Any:
        row = _rows(frame)[i]
        return row.get(column) if isinstance(row, dict) else None


class AttributeEcosystem:
    """Records are instances of `cls`, built by keyword and read by
    attribute; tables are lists of them."""

    name = "attribute"

    def __init__(self, cls: type) -> None:
        self.cls = cls

    def accepts(self, obj: Any) -> bool:
        return obj is self.cls

    def to_model(self, obj: Any) -> RowSchema | TableSchema:
        from ..adaptors.dataclass import schema_of
        return schema_of(obj)

    def build_row(self, schema: RowSchema, values: dict[str, Any]) -> Any:
        return self.cls(**values)

    def build_frame(self, table: TableSchema, columns: dict[str, list[Any]]) -> list[Any]:
        names = list(columns)
        n = len(columns[names[0]]) if names else 0
        return [self.cls(**{name: columns[name][i] for name in names}) for i in range(n)]

    def validate_row(self, schema: RowSchema, row: Any) -> list[Problem]:
        if not isinstance(row, self.cls):
            return [Problem("", f"an instance of {self.cls.__name__}", row)]
        return row_problems(schema, row)

    def validate_frame(self, table: TableSchema, frame: Any,
                       parents: dict[str, Any] | None = None) -> list[Problem]:
        try:
            rows = _rows(frame)
        except TypeError:
            return [Problem("", "a list of records", frame)]
        return frame_problems(table, rows, self.column_names(frame),
                              lambda row: self.validate_row(table.row, row),
                              lambda row, col: getattr(row, col, None),
                              {k: _rows(v) for k, v in (parents or {}).items()})

    def row_count(self, frame: Any) -> int:
        return len(_rows(frame))

    def column_names(self, frame: Any) -> tuple[str, ...] | None:
        if dataclasses.is_dataclass(self.cls):
            return tuple(f.name for f in dataclasses.fields(self.cls))
        return None

    def cell(self, frame: Any, i: int, column: str) -> Any:
        return getattr(_rows(frame)[i], column, None)


__all__ = ["AttributeEcosystem", "PlainEcosystem"]
