# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A TypedDict as a row schema: its keys with their hints, optional
keys not required, `Optional` as nullable, `Annotated` markers as
constraints; members are plain dicts, checked by the neutral
checker."""
from __future__ import annotations

import typing
from typing import Any

from ...adaptor_priority import STRUCTURAL, priority
from ..ecosystems.plain import PlainEcosystem
from ..languages import RowLanguage
from ..model import RowSchema
from ._hints import read_record


def schema_of(cls: Any) -> RowSchema:
    """The row schema of a TypedDict."""
    fields, definitions = read_record(cls)
    for f in fields:
        if f.constraints.regex is not None:
            raise ValueError(f"{cls.__name__}.{f.name}: a regular expression on a TypedDict key "
                             "has no validator to hold it to; use a pydantic model or a JSON Schema")
    total = getattr(cls, "__total__", True)
    return RowSchema(cls.__name__, tuple(fields), column_policy="exact" if total else "open",
                     definitions=definitions)


@priority(STRUCTURAL)
def adapt(obj: Any) -> RowLanguage | None:
    """The row language of a TypedDict, or None for anything else."""
    if not typing.is_typeddict(obj):
        return None
    return RowLanguage(schema_of(obj), PlainEcosystem(), obj.__name__)


__all__ = ["adapt", "schema_of"]
