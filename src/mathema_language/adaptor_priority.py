# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The order mathema asks the language adaptors in: each carries
`__mathema_adaptor_priority__`, higher asked first, ties by entry-point
name. The bands this package uses, and documents for others:
`LIBRARY` (100) for an adaptor that recognises a library's own model
classes (pydantic, SQLAlchemy, Django), `DOCUMENT` (50) for a schema
written as data (a JSON Schema), and `STRUCTURAL` (0) for one that
reads any class of a standard shape (a dataclass, a TypedDict) or a
plain annotation."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

LIBRARY = 100
DOCUMENT = 50
STRUCTURAL = 0

F = TypeVar("F", bound=Callable[..., Any])


def priority(value: int) -> Callable[[F], F]:
    """Mark an adaptor with the priority mathema asks it at."""
    def mark(adapt: F) -> F:
        setattr(adapt, "__mathema_adaptor_priority__", value)  # noqa: B010
        return adapt
    return mark


__all__ = ["DOCUMENT", "LIBRARY", "STRUCTURAL", "priority"]
