# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A shape's canonical picture is the same language as the picture it
was read from, and reads back to itself: two quoted texts written side
by side never merge into one, whatever counts they carry. A count is
bounded, so a shape's members, draws, pattern and term are written in
bounded time, and a picture past the bound is refused by name."""
import random
import re

import pytest

from mathema_language.text import _algebra
from mathema_language.text.shape import Shape, ShapeError, shape_language, shape_refusal


@pytest.mark.parametrize("picture", ["'ab'{1}'cd'{2}", "'ab''cd'{2}", "'ab'\\K'cd'{2}",
                                     "'a-'{1}'cd'{2}", "'-a''cd'{2}", "'ab'9'cd'{2}",
                                     "'a''b'{2}", "'x''y'{2,3}'z'"])
def test_the_canonical_picture_has_the_same_members_and_reads_back_to_itself(picture):
    shape = Shape(picture)
    again = Shape(shape.shape)
    assert again.shape == shape.shape
    texts = set(shape.members()) | set(again.members())
    texts |= {"abcdcd", "ab'cdab'cd", "abcd", "ab'cd", "a-cdcd", "-acdcd", "ab9cdcd", "a'b'b", "a'bb"}
    for text in texts:
        assert shape.matches(text) == again.matches(text), (picture, shape.shape, text)


def _picture(rng, depth=0):
    atoms = ["A", "a", "9", "X", "-", " ", "'ab'", "'K'", "'-.'", "\\[", "\\'", "\\K", "\\9",
             "'''", ".", "_", "'x''y'", "\\\\", "'cd'"]
    out = ""
    for _ in range(rng.randint(1, 4)):
        atom = "[" + _picture(rng, depth + 1) + "]" if depth < 2 and rng.random() < 0.2 else rng.choice(atoms)
        roll = rng.random()
        if roll < 0.2:
            atom += f"{{{rng.randint(1, 3)}}}"
        elif roll < 0.3:
            lo = rng.randint(0, 2)
            atom += f"{{{lo},{lo + rng.randint(0 if lo else 1, 2)}}}"
        elif roll < 0.35:
            atom += f"{{{rng.randint(0, 2)}+}}"
        out += atom
    return out


def test_on_generated_pictures_the_canonical_text_keeps_the_language():
    rng = random.Random(9)
    pool = "aZ9 -'[K.x_\\cdyé"
    for _ in range(800):
        picture = _picture(rng)
        try:
            shape = Shape(picture, "ascii" if rng.random() < 0.5 else "unicode")
        except ShapeError:
            continue
        again = Shape(shape.shape, shape.base)
        assert again.shape == shape.shape, (picture, shape.shape, again.shape)
        texts = set(shape.members()) | {shape.draw(rng) for _ in range(10)}
        texts |= {t for t, _ in shape.near_misses(rng)}
        texts |= {"".join(rng.choice(pool) for _ in range(rng.randint(0, 8))) for _ in range(30)}
        term = again.term()
        for text in texts:
            want = shape.matches(text)
            assert again.matches(text) == want, (picture, shape.shape, text)
            assert (re.fullmatch(again.pattern, text) is not None) == want, (picture, text)
            key = "language" if term["exact"] else "at_least"
            if term["exact"]:
                assert _algebra.member(term, text, key) == want, (picture, text)


@pytest.mark.parametrize("picture", ["9{4294967296}", "9{99999999999}", "9{99999999999+}",
                                     "9{1," + "9" * 5000 + "}", "[[9{100}]{100}]{100}"])
def test_a_count_past_the_bound_is_refused_by_name(picture):
    with pytest.raises(ShapeError, match="count"):
        Shape(picture)
    with pytest.raises(ShapeError):
        shape_language(picture, "ascii")
    refusal = shape_refusal("ascii", (picture,))
    assert refusal is not None and "count" in refusal


def test_a_shape_at_the_bound_is_written_in_full():
    shape = Shape("9{1000}")
    assert len(shape.draw(random.Random(0))) == 1000
    assert all(len(m) == 1000 for m in shape.members())
    assert re.fullmatch(shape.pattern, "1" * 1000)
