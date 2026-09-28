# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A search result as the search service returns it, a TypedDict."""
from __future__ import annotations

from typing import Annotated, TypedDict

from annotated_types import Ge, Le


class SearchHit(TypedDict):
    title: str
    score: Annotated[float, Ge(0.0), Le(1.0)]
    clicks: Annotated[int, Ge(0)]


def rank(hit: SearchHit) -> float:
    """Where the hit sorts: relevance first, popularity after."""
    return hit["score"] * 10 + hit["clicks"] / 1000
