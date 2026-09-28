# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The standard-library ecosystems, the reference every other one is
tested against: `PlainEcosystem` (a record is a dict) and
`AttributeEcosystem` (a record is an instance of a class built by
keyword). Both validate with the neutral checker."""
from __future__ import annotations

from typing import Any

from ..._surface import Problem
from ..checks import row_problems
from ..model import RowSchema


class PlainEcosystem:
    """Records are mappings."""

    name = "plain"

    def accepts(self, obj: Any) -> bool:
        return isinstance(obj, RowSchema)

    def to_model(self, obj: Any) -> RowSchema:
        if not self.accepts(obj):
            raise TypeError(f"not a neutral schema: {obj!r}")
        return obj  # type: ignore[no-any-return]

    def build_row(self, schema: RowSchema, values: dict[str, Any]) -> dict[str, Any]:
        return dict(values)

    def validate_row(self, schema: RowSchema, row: Any) -> list[Problem]:
        if not isinstance(row, dict):
            return [Problem("", "a mapping record", row)]
        return row_problems(schema, row)


class AttributeEcosystem:
    """Records are instances of `cls`, built by keyword and read by
    attribute."""

    name = "attribute"

    def __init__(self, cls: type) -> None:
        self.cls = cls

    def accepts(self, obj: Any) -> bool:
        return obj is self.cls

    def to_model(self, obj: Any) -> RowSchema:
        from ..adaptors.dataclass import schema_of
        return schema_of(obj)

    def build_row(self, schema: RowSchema, values: dict[str, Any]) -> Any:
        return self.cls(**values)

    def validate_row(self, schema: RowSchema, row: Any) -> list[Problem]:
        if not isinstance(row, self.cls):
            return [Problem("", f"an instance of {self.cls.__name__}", row)]
        return row_problems(schema, row)


__all__ = ["AttributeEcosystem", "PlainEcosystem"]
