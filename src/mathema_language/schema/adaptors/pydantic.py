# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A pydantic model as a row schema: its fields with their
annotations, `Field(...)` and `annotated_types` markers as
constraints, `extra="forbid"` as the exact column policy; members
are validated by the model itself."""
from __future__ import annotations

import sys
from typing import Any

from ..._priority import LIBRARY, priority
from ..ecosystems.pydantic import PydanticEcosystem
from ..languages import RowLanguage
from ..model import RowSchema
from ._hints import pydantic_fields


def _is_model(obj: Any) -> bool:
    """Whether `obj` is a pydantic model class, decided without
    importing pydantic: no import means no model can exist."""
    pydantic = sys.modules.get("pydantic")
    if pydantic is None or not isinstance(obj, type):
        return False
    return issubclass(obj, pydantic.BaseModel)


def schema_of(model: type) -> RowSchema:
    """The row schema of a pydantic model."""
    config = getattr(model, "model_config", {}) or {}
    policy = "exact" if config.get("extra") == "forbid" else "open"
    return RowSchema(model.__name__, tuple(pydantic_fields(model)), column_policy=policy)


@priority(LIBRARY)
def adapt(obj: Any) -> RowLanguage | None:
    """The row language of a pydantic model, or None for anything else."""
    if not _is_model(obj):
        return None
    return RowLanguage(schema_of(obj), PydanticEcosystem(obj), obj.__name__)


__all__ = ["adapt", "schema_of"]
