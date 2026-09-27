# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The refinement keys this package serves inside `L[...]`, each
registered under mathema's `mathema.language_refinements` group and
built from mathema's `RefinedLanguage` kit. `len`: the length in code
points, Python's `len`, the plain member of length `n` one repeated
simple character the language admits (`"a" * 80`), a built member a run
of the language's own members cut to length."""
from __future__ import annotations

import random
from typing import Any

from ._surface import RefinedLanguage, domain_bound_from_json

_SIMPLE = ("a", "0", "x", "A", " ")


def _range(interval: Any) -> tuple[int, int | None]:
    lo, hi = interval[0], interval[1]
    first = int(lo) if getattr(interval, "closed_lo", True) else int(lo) + 1
    if hi == float("inf"):
        return first, None
    return first, int(hi) if getattr(interval, "closed_hi", True) else int(hi) - 1


def length(language: Any, interval: Any) -> Any:
    """The members of `language` whose length in code points lies in
    `interval`."""

    def plain(n: int) -> str | None:
        for ch in _SIMPLE:
            if language.contains(ch * n):
                return ch * n
        return None

    def build(rng: random.Random, n: int) -> str | None:
        for _ in range(100):
            s = language.sample(rng)
            if isinstance(s, str) and len(s) == n:
                return s
        for _ in range(100):
            run = ""
            while len(run) < n:
                piece = language.sample(rng)
                if not isinstance(piece, str):
                    return None
                run += piece or _SIMPLE[0]
            if language.contains(run[:n]):
                return run[:n]
        return None

    lo, hi = _range(interval)
    schema = {"minLength": lo, **({"maxLength": hi} if hi is not None else {})}
    return RefinedLanguage(language, "len", interval, measure=len, plain=plain, build=build,
                           schema=schema, hazard_kind="length")


def length_bound(lo: int, hi: int | None) -> Any:
    """The interval of lengths from `lo` to `hi` (None for no upper
    bound), as a refinement reads it."""
    return domain_bound_from_json({"lo": float(lo), "hi": float("inf") if hi is None else float(hi),
                                   "closed_lo": True, "closed_hi": True})


__all__ = ["length", "length_bound"]
