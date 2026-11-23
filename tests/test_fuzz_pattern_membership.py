# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A pattern's membership, its term's own matcher, agrees with the
independent direct reading in `tests/_pattern_oracle.py` on generated
pictures, some with a bound alphabet, over texts that hold the empty
text, astral characters, lone surrogates, combining marks, CR and LF,
NUL and DEL, fullwidth and Arabic-Indic digits, and on long repeats.
Seeded; a small budget by default, the full one under `heavy`."""
import random

import pytest

from mathema_language.text.pattern import Pattern, PatternError
from tests import _fuzz
from tests._pattern_oracle import _draw_picture, reads

SEED = 1
POOL = "aZ9 -'[K.x_é٣\n\r\\ŕ́\ud800\U0001f600\U00010400ǅ\x00\x7f１"
BINDINGS = ['lower + digit + "_"', "hexdigit", 'upper + "é"', "unicode_alpha", 'printable + "\\n"', '"\\ud800"']


def _check(pictures: int) -> tuple[int, int]:
    rng = random.Random(SEED)
    checked = texts_seen = 0
    for _ in range(pictures):
        picture = _draw_picture(rng)
        for base in ("ascii", "unicode"):
            bound = {}
            written = picture
            if rng.random() < 0.3:
                written, bound = picture + "W{0,3}", {"W": rng.choice(BINDINGS)}
            try:
                pattern = Pattern(written, base, **bound)
            except (PatternError, ValueError):
                continue
            checked += 1
            language = pattern.language()
            texts = {pattern.draw(rng) for _ in range(5)} | set(pattern.members())
            texts |= {t for t, _ in pattern.near_misses(rng)}
            texts |= {"".join(rng.choice(POOL) for _ in range(rng.randint(0, 8))) for _ in range(15)}
            texts |= {t + "\n" for t in sorted(texts)[:5]}
            for text in texts:
                texts_seen += 1
                assert language.contains(text) == reads(pattern, text), (written, base, bound, text)
    return checked, texts_seen


@pytest.mark.parametrize("picture, text", [
    ("a{0+}", "a" * 9000), ("X{0+}", "\U0001f600" * 5000), ("[a]{0,5000}", "a" * 5000),
    ("[a]{0,5000}", "a" * 5001), ("['ab'['c']]{0,3000}", "abc" * 1000 + "ab" * 999),
    ("[[a]{0,50}]{0,50}", "a" * 2400 + "b"), ("[a{0+}]{0,99}", "a" * 3000 + "b"),
    ("[[X]{1,9}]{1,999}", "x" * 8000 + "\n"), ("X{0,9000}a", "b" * 8999 + "a"),
    ("[X{0,30}X{0,30}]{0,100}", "x" * 5000),
])
def test_long_repeats_agree_with_the_direct_reading(picture, text):
    pattern = Pattern(picture, "unicode")
    assert pattern.language().contains(text) == reads(pattern, text)


def test_generated_pictures_agree_with_the_direct_reading():
    checked, texts = _check(150)
    _fuzz.report("pattern membership", SEED, pictures=checked, texts=texts)
    assert checked >= 150


@_fuzz.heavy
def test_generated_pictures_agree_with_the_direct_reading_at_full_size():
    checked, texts = _check(3000)
    _fuzz.report("pattern membership, full", SEED, pictures=checked, texts=texts)
    assert checked >= 3000
