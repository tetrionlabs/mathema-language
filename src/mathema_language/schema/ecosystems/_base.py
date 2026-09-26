# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The `Ecosystem` protocol: the contract a library implements so
that its records and tables are members of a `RowLanguage` or a
`FrameLanguage`. The neutral checker serves the standard-library
ecosystems; a library with a validator of its own (pydantic, JSON
Schema, a database) validates through that, so the constraint
semantics are the library's."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ..._surface import Problem
from ..model import RowSchema, TableSchema


@runtime_checkable
class Ecosystem(Protocol):
    """`name` is the ecosystem's name in a record. `accepts` says
    whether a schema object is this ecosystem's without importing
    anything, `to_model` reads it into the neutral model, `build_row`
    and `build_frame` make a record and a table from neutral values,
    `validate_row` and `validate_frame` report every problem with
    one, and `row_count`, `column_names` and `cell` read a table."""

    name: str

    def accepts(self, obj: Any) -> bool: ...

    def to_model(self, obj: Any) -> RowSchema | TableSchema: ...

    def build_row(self, schema: RowSchema, values: dict[str, Any]) -> Any: ...

    def build_frame(self, table: TableSchema, columns: dict[str, list[Any]]) -> Any: ...

    def validate_row(self, schema: RowSchema, row: Any) -> list[Problem]: ...

    def validate_frame(self, table: TableSchema, frame: Any,
                       parents: dict[str, Any] | None = None) -> list[Problem]: ...

    def row_count(self, frame: Any) -> int: ...

    def column_names(self, frame: Any) -> tuple[str, ...] | None: ...

    def cell(self, frame: Any, i: int, column: str) -> Any: ...


__all__ = ["Ecosystem"]
