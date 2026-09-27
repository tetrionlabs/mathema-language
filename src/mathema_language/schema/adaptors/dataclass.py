# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A dataclass as a row schema: its fields with their hints, `Optional`
as nullable, `Annotated` markers as constraints, defaults kept;
members are instances of the class, checked by the neutral checker.
A regular expression in a marker is refused at adaptation, since the
standard library has no validator to hold it to."""
from __future__ import annotations

import dataclasses
from typing import Any

from ..._priority import STRUCTURAL, priority
from ..ecosystems.plain import AttributeEcosystem
from ..languages import RowLanguage
from ..model import RowSchema
from ._hints import dataclass_fields


def schema_of(cls: type) -> RowSchema:
    """The row schema of a dataclass."""
    fields = dataclass_fields(cls)
    for f in fields:
        if f.constraints.regex is not None:
            raise ValueError(f"{cls.__name__}.{f.name}: a regular expression on a dataclass field "
                             "has no validator to hold it to; use a pydantic model or a JSON Schema")
    return RowSchema(cls.__name__, tuple(fields))


@priority(STRUCTURAL)
def adapt(obj: Any) -> RowLanguage | None:
    """The row language of a dataclass, or None for anything else."""
    if not (isinstance(obj, type) and dataclasses.is_dataclass(obj)):
        return None
    return RowLanguage(schema_of(obj), AttributeEcosystem(obj), obj.__name__)


__all__ = ["adapt", "schema_of"]
