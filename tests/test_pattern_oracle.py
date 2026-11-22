# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A pattern's membership, its term's own matcher, agrees with the
independent character-by-character reading in `tests/_pattern_oracle.py`:
the claims written there hold when mathema checks them, and the two
agree directly on every vector picture and on a fuzz of generated
pictures and texts."""
import random
import re

import pytest

from mathema_language.text.pattern import Pattern, PatternError
from tests import _pattern_oracle as oracle


def _declared(fn) -> list[str]:
    section = fn.__doc__.split("Claims:")[1]
    return re.findall(r"^\s+(\w+): ", section, flags=re.MULTILINE)


@pytest.mark.parametrize("fn", [oracle.agrees, oracle.agrees_on_its_own_texts], ids=lambda fn: fn.__name__)
def test_every_declared_agreement_claim_holds(fn):
    mathema = pytest.importorskip("mathema")
    names = _declared(fn)
    assert len(names) >= 4
    verdicts = {p.name: (p.verdict, p.note) for p in mathema.check(fn, claims=[]).probes if p.name in names}
    assert sorted(verdicts) == sorted(names)
    assert {name: v for name, (v, _) in verdicts.items() if v not in ("holds", "proven")} == {}, verdicts


@pytest.mark.parametrize("base", ["ascii", "unicode"])
@pytest.mark.parametrize("picture", oracle.VECTORS)
def test_every_vector_picture_agrees_with_the_direct_reading(picture, base):
    if base == "ascii" and not picture.isascii():
        with pytest.raises(PatternError):
            Pattern(picture, base)
        return
    assert oracle.agrees_on_its_own_texts(picture, base)


def test_generated_pictures_agree_with_the_direct_reading_on_their_texts():
    rng = random.Random(20261122)
    checked = 0
    for _ in range(600):
        picture = oracle._draw_picture(rng)
        for base in ("ascii", "unicode"):
            try:
                Pattern(picture, base)
            except PatternError:
                continue
            assert oracle.agrees_on_its_own_texts(picture, base), (picture, base)
            checked += 1
    assert checked >= 600
