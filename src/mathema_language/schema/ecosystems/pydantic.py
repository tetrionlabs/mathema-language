# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The pydantic ecosystem: a record is an instance of the model, and
membership is the model's own validation,
so the constraint semantics are pydantic's. pydantic is imported
inside the methods that need it, never at module level."""
from __future__ import annotations

from typing import Any

from ..._surface import Problem
from ..model import RowSchema


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

    def to_model(self, obj: Any) -> RowSchema:
        from ..adaptors.pydantic import schema_of
        return schema_of(obj)

    def build_row(self, schema: RowSchema, values: dict[str, Any]) -> Any:
        return self.model.model_construct(**values)  # type: ignore[attr-defined]

    def _values(self, row: Any) -> dict[str, Any] | None:
        """The row as the data a caller would hand the model, nested
        models dumped too, so every level is validated; extras kept, so
        a column the model forbids is still refused. None when the row
        is too deep for pydantic to dump."""
        try:
            values: dict[str, Any] = dict(row.model_dump(mode="python", warnings=False))
        except RecursionError:
            return None
        except Exception:
            values = dict(getattr(row, "__dict__", {}))
        extra = getattr(row, "__pydantic_extra__", None)
        if extra:
            values.update(extra)
        return values

    def validate_row(self, schema: RowSchema, row: Any) -> list[Problem]:
        from pydantic import ValidationError
        if not isinstance(row, self.model):
            return [Problem("", f"an instance of {self.model.__name__}", row)]
        values = self._values(row)
        if values is None:
            return [Problem("", "within pydantic's own depth limit", type(row).__name__)]
        try:
            self.model.model_validate(values)  # type: ignore[attr-defined]
        except RecursionError:
            return [Problem("", "within pydantic's own depth limit", type(row).__name__)]
        except ValidationError as e:
            return [Problem(_path(tuple(err["loc"])), err["msg"], err.get("input"))
                    for err in e.errors()]
        return []


__all__ = ["PydanticEcosystem"]
