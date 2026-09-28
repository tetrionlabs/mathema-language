# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""`TextLanguage`: mathema's `StringLanguage` kit with the text hazard
corpus, category-based sampling across the planes, and shrinking that
prefers the language's simplest character.
"""
from __future__ import annotations

import random
from collections.abc import Iterator
from dataclasses import dataclass
from typing import cast

from .._surface import HazardValue, StringLanguage
from . import generate as _generate
from .hazards import TEXT_HAZARDS


@dataclass(frozen=True)
class TextLanguage(StringLanguage):
    """A language of `str` values built on the kit. `categories` are
    the Unicode general categories random members draw characters
    from (empty: the character pool only) and `planes` the planes they
    come from; `category_share` is how often a draw goes by category
    rather than by pool. `simplest` is the member character shrinking
    substitutes first. `extra_hazards` are `HazardValue`s this language
    adds to the shared corpora."""
    categories: tuple[str, ...] = ()
    planes: tuple[int, ...] = (0,)
    category_share: float = 0.5
    simplest: str = "a"
    extra_hazards: tuple[HazardValue, ...] = ()

    def hazards(self) -> tuple[HazardValue, ...]:
        seen: set[str] = set()
        out: list[HazardValue] = []
        for hazard in (*super().hazards(), *TEXT_HAZARDS, *self.extra_hazards):
            if hazard.value in seen or not self.contains(hazard.value):
                continue
            seen.add(hazard.value)
            out.append(hazard)
        return tuple(out)

    def sample(self, rng: random.Random) -> str:
        if self.categories and rng.random() < self.category_share:
            for _ in range(20):
                s = _generate.draw(rng, self.categories, self.planes)
                if self.contains(s):
                    return s
        return cast(str, super().sample(rng))

    def shrink(self, value: object) -> Iterator[str]:
        """Smaller members one at a time: the base kit's deletions first,
        largest first, then each character replaced by this language's
        simplest one, then the base kit's other candidates; a caller
        that stops at the first useful candidate checks only the ones
        before it."""
        if not isinstance(value, str):
            return
        seen = {value}
        for s in super().shrink(value):
            if len(s) < len(value) and s not in seen:
                seen.add(s)
                yield s
        for i, ch in enumerate(value):
            if ch != self.simplest:
                s = value[:i] + self.simplest + value[i + 1:]
                if s not in seen and self.contains(s):
                    seen.add(s)
                    yield s
        for s in super().shrink(value):
            if s not in seen:
                seen.add(s)
                yield s

__all__ = ["TextLanguage"]
