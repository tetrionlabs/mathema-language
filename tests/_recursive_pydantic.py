# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A self-referential pydantic model with a bounded children list."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int
    children: list[PNode] = Field(default_factory=list, max_length=3)


PNode.model_rebuild()
