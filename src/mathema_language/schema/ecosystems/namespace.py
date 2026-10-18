# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Records as `argparse.Namespace` objects, read by attribute and checked
by the neutral checker. A field whose argument type is a callable the
neutral model has no type for (a `pathlib.Path`, a custom parser) is
drawn as text and converted by that callable, as argparse converts it."""
from __future__ import annotations

import argparse
from typing import Any

from ..._surface import Problem
from ..checks import row_problems
from ..model import RowSchema


def _converted(convert: Any, text: str) -> Any:
    """Intent:
        `text` passed through the argument's type converter, or `text` unchanged when the
        converter raises, standing for a value argparse would not have produced.
    """
    try:
        return convert(text)
    except Exception:
        return text


class NamespaceEcosystem:
    """Records are `argparse.Namespace` objects."""

    name = "argparse"

    def __init__(self, converters: dict[str, Any] | None = None) -> None:
        self.converters = dict(converters or {})

    def accepts(self, obj: Any) -> bool:
        return isinstance(obj, RowSchema)

    def to_model(self, obj: Any) -> RowSchema:
        if not self.accepts(obj):
            raise TypeError(f"not a neutral schema: {obj!r}")
        return obj  # type: ignore[no-any-return]

    def build_row(self, schema: RowSchema, values: dict[str, Any]) -> argparse.Namespace:
        converted = {}
        for name, value in values.items():
            convert = self.converters.get(name)
            if convert is not None and isinstance(value, str):
                value = _converted(convert, value)
            elif convert is not None and isinstance(value, list):
                value = [_converted(convert, v) if isinstance(v, str) else v for v in value]
            converted[name] = value
        return argparse.Namespace(**converted)

    def validate_row(self, schema: RowSchema, row: Any) -> list[Problem]:
        if not isinstance(row, argparse.Namespace):
            return [Problem("", "an argparse.Namespace", row)]
        values = dict(vars(row))
        for name, convert in self.converters.items():
            value = values.get(name)
            if isinstance(convert, type) and isinstance(value, convert):
                values[name] = str(value)
            elif isinstance(convert, type) and isinstance(value, list) \
                    and all(isinstance(v, convert) for v in value):
                values[name] = [str(v) for v in value]
        return row_problems(schema, values)


__all__ = ["NamespaceEcosystem"]
