# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The pydantic shape the row-language tests run over."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class OrderModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    qty: Annotated[int, Field(ge=1, le=10)]
    price: Annotated[float, Field(ge=0.0)]
    sku: Annotated[str, Field(max_length=8)]
    kind: Literal["web", "shop"]
    note: str | None = None
