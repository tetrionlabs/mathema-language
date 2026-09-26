# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Drawing random members of a text language by Unicode category
across the planes, so a sample reaches the astral planes and the
categories a fixed pool never would.
"""
from __future__ import annotations

import random
import unicodedata

#: the code-point range of each plane that holds assigned characters
PLANES: dict[int, tuple[int, int]] = {
    0: (0x0000, 0xFFFF),
    1: (0x10000, 0x1FFFF),
    2: (0x20000, 0x2FFFF),
    3: (0x30000, 0x3FFFF),
    14: (0xE0000, 0xE01EF),
    15: (0xF0000, 0xFFFFD),
    16: (0x100000, 0x10FFFD),
}

#: the categories a draw never produces unless asked for: unassigned
#: code points and surrogates
_ONLY_ON_REQUEST = frozenset({"Cn", "Cs"})


def draw_char(rng: random.Random, categories: tuple[str, ...],
              planes: tuple[int, ...]) -> str:
    """One character whose general category is in `categories` (any
    assigned category when empty), from a plane chosen among `planes`;
    a category in `_ONLY_ON_REQUEST` is produced only when named.
    Falls back to the letter `a` when two hundred draws find nothing,
    which a caller's membership check then judges."""
    wanted = frozenset(categories)
    for _ in range(200):
        plane = rng.choice(planes)
        lo, hi = PLANES.get(plane, (plane * 0x10000, plane * 0x10000 + 0xFFFF))
        ch = chr(rng.randint(lo, hi))
        category = unicodedata.category(ch)
        if category in _ONLY_ON_REQUEST and category not in wanted:
            continue
        if wanted and category not in wanted:
            continue
        return ch
    return "a"


def draw_length(rng: random.Random) -> int:
    """A member length: short most of the time, occasionally long
    enough to reach buffer-sized behaviour."""
    if rng.random() < 0.1:
        return rng.randint(64, 300)
    return rng.randint(0, 12)


def draw(rng: random.Random, categories: tuple[str, ...] = (),
         planes: tuple[int, ...] = (0,), length: int | None = None) -> str:
    """A string of `length` characters (drawn by `draw_length` when
    None), each from `draw_char`."""
    n = draw_length(rng) if length is None else length
    return "".join(draw_char(rng, categories, planes) for _ in range(n))


__all__ = ["PLANES", "draw", "draw_char", "draw_length"]
