# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The pydantic ecosystem: a record is an instance of the model, a
table a list of them, and membership is the model's own validation,
so the constraint semantics are pydantic's. pydantic is imported
inside the methods that need it, never at module level."""
from __future__ import annotations

from typing import Any

from ..._surface import Problem
from ..checks import frame_problems
from ..model import RowSchema, TableSchema


def _path(loc: tuple[Any, ...]) -> str:
    out = ""
    for part in loc:
        out += f"[{part}]" if isinstance(part, int) else f".{part}"
    return out


class PydanticEcosystem:
    """Records are instances of `model`, built without validation so
    that a non-member can exist to be explained; validation runs the
    model over the record's own attributes."""

    name = "pydantic"

    def __init__(self, model: type) -> None:
        self.model = model

    def accepts(self, obj: Any) -> bool:
        return obj is self.model

    def to_model(self, obj: Any) -> RowSchema | TableSchema:
        from ..adaptors.pydantic import schema_of
        return schema_of(obj)

    def build_row(self, schema: RowSchema, values: dict[str, Any]) -> Any:
        return self.model.model_construct(**values)  # type: ignore[attr-defined]

    def _build_frame(self, table: TableSchema, columns: dict[str, list[Any]]) -> list[Any]:
        names = list(columns)
        n = len(columns[names[0]]) if names else 0
        return [self.build_row(table.row, {name: columns[name][i] for name in names})
                for i in range(n)]

    def _values(self, row: Any) -> dict[str, Any]:
        values = dict(getattr(row, "__dict__", {}))
        extra = getattr(row, "__pydantic_extra__", None)
        if extra:
            values.update(extra)
        return values

    def validate_row(self, schema: RowSchema, row: Any) -> list[Problem]:
        from pydantic import ValidationError
        if not isinstance(row, self.model):
            return [Problem("", f"an instance of {self.model.__name__}", row)]
        try:
            self.model.model_validate(self._values(row))  # type: ignore[attr-defined]
        except ValidationError as e:
            return [Problem(_path(tuple(err["loc"])), err["msg"], err.get("input"))
                    for err in e.errors()]
        return []

    def _validate_frame(self, table: TableSchema, frame: Any,
                       parents: dict[str, Any] | None = None) -> list[Problem]:
        if not isinstance(frame, (list, tuple)):
            return [Problem("", "a list of records", frame)]
        return frame_problems(table, list(frame), self._column_names(frame),
                              lambda row: self.validate_row(table.row, row),
                              lambda row, col: getattr(row, col, None),
                              {k: list(v) for k, v in (parents or {}).items()})

    def _row_count(self, frame: Any) -> int:
        return len(frame)

    def _column_names(self, frame: Any) -> tuple[str, ...] | None:
        return tuple(self.model.model_fields)  # type: ignore[attr-defined]

    def _cell(self, frame: Any, i: int, column: str) -> Any:
        return getattr(frame[i], column, None)


__all__ = ["PydanticEcosystem"]
