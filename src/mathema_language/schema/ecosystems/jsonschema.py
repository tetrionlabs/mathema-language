# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The JSON Schema ecosystem: a record is a dict, and membership is `jsonschema`'s draft 2020-12 validator over
the schema as written, so the constraint semantics are the
validator's. `jsonschema` is imported inside the methods that need
it, never at module level."""
from __future__ import annotations

from typing import Any

from ..._surface import Problem
from ..model import RowSchema


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

    def to_model(self, obj: Any) -> RowSchema:
        from ..adaptors.jsonschema import schema_of
        return schema_of(obj)

    def build_row(self, schema: RowSchema, values: dict[str, Any]) -> dict[str, Any]:
        return dict(values)

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


__all__ = ["JsonSchemaEcosystem"]
