# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The pydantic ecosystem: a record is an instance of the model, and
membership is the model's own validation,
so the constraint semantics are pydantic's. pydantic is imported
inside the methods that need it, never at module level."""
from __future__ import annotations

from typing import Any

from ..._surface import Problem, Refusal
from ..model import RowSchema


def _path(loc: tuple[Any, ...]) -> str:
    """Intent:
        A pydantic error location in the path grammar: `[i]` for an index, `.name` for a field,
        joined in order (`.items[0].sku`).
    """
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
        """Intent:
            An instance of the model holding `values`, built without validation; a key the
            model does not declare is kept among its extra attributes whatever the model's
            `extra` setting, so validation sees it as the caller handed it over.
        """
        declared = getattr(self.model, "model_fields", {})
        row = self.model.model_construct(  # type: ignore[attr-defined]
            **{k: v for k, v in values.items() if k in declared})
        extra = {k: v for k, v in values.items() if k not in declared}
        if extra:
            object.__setattr__(row, "__pydantic_extra__",
                               {**(getattr(row, "__pydantic_extra__", None) or {}), **extra})
        return row

    def _values(self, row: Any) -> dict[str, Any] | None:
        """Intent:
            The row as the data a caller would hand the model, nested models dumped too and
            extra attributes kept, or None when the row is too deep for pydantic to dump.

        Notes:
            Dumping nested models means every level is validated, and keeping extras means a
            column the model forbids is still refused. A row that fails to dump falls back to
            its `__dict__`.
        """
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

    def refusal(self) -> Refusal:
        """A function refuses an invalid record with the library's own
        validation error."""
        from pydantic import ValidationError
        return Refusal("pydantic ValidationError", raises=ValidationError)

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
