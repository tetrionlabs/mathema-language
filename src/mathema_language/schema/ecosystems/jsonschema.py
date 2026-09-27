# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The JSON Schema ecosystem: a record is a dict, a table a list of
them, and membership is `jsonschema`'s draft 2020-12 validator over
the schema as written, so the constraint semantics are the
validator's. `jsonschema` is imported inside the methods that need
it, never at module level."""
from __future__ import annotations

from typing import Any

from ..._surface import Problem
from ..checks import frame_problems
from ..model import RowSchema, TableSchema


def _path(parts: Any) -> str:
    out = ""
    for part in parts:
        out += f"[{part}]" if isinstance(part, int) else f".{part}"
    return out


class JsonSchemaEcosystem:
    """Records are dicts validated against `schema`."""

    name = "jsonschema"

    def __init__(self, schema: dict[str, Any]) -> None:
        self.schema = schema
        self._validator: Any = None

    def accepts(self, obj: Any) -> bool:
        return obj is self.schema

    def to_model(self, obj: Any) -> RowSchema | TableSchema:
        from ..adaptors.jsonschema import schema_of
        return schema_of(obj)

    def build_row(self, schema: RowSchema, values: dict[str, Any]) -> dict[str, Any]:
        return dict(values)

    def _build_frame(self, table: TableSchema, columns: dict[str, list[Any]]) -> list[dict[str, Any]]:
        names = list(columns)
        n = len(columns[names[0]]) if names else 0
        return [{name: columns[name][i] for name in names} for i in range(n)]

    def _validator_for(self) -> Any:
        if self._validator is None:
            from jsonschema import Draft202012Validator
            self._validator = Draft202012Validator(self.schema)
        return self._validator

    def validate_row(self, schema: RowSchema, row: Any) -> list[Problem]:
        if not isinstance(row, dict):
            return [Problem("", "a mapping record", row)]
        try:
            return [Problem(_path(err.absolute_path), err.message, err.instance)
                    for err in self._validator_for().iter_errors(row)]
        except RecursionError:
            return [Problem("", "within jsonschema's own depth limit", "a nested document")]

    def _validate_frame(self, table: TableSchema, frame: Any,
                       parents: dict[str, Any] | None = None) -> list[Problem]:
        if not isinstance(frame, (list, tuple)):
            return [Problem("", "a list of records", frame)]
        names: list[str] = []
        for row in frame:
            if isinstance(row, dict):
                for k in row:
                    if k not in names:
                        names.append(str(k))
        return frame_problems(table, list(frame), tuple(names) if frame else None,
                              lambda row: self.validate_row(table.row, row),
                              lambda row, col: row.get(col) if isinstance(row, dict) else None,
                              {k: list(v) for k, v in (parents or {}).items()})

    def _row_count(self, frame: Any) -> int:
        return len(frame)

    def _column_names(self, frame: Any) -> tuple[str, ...] | None:
        return tuple(self.schema.get("properties", {}))

    def _cell(self, frame: Any, i: int, column: str) -> Any:
        row = frame[i]
        return row.get(column) if isinstance(row, dict) else None


__all__ = ["JsonSchemaEcosystem"]
