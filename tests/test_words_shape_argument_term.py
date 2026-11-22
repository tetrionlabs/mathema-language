# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A shape given to a pattern word, `matches (shape("A9"))`, states one
term on every supported Python: the shape's own term under the word's
predicate. Where a symbol stands for a Unicode class that differs
between versions it is a pair of bounds, as the shape word gives, never
an exact term built from this interpreter's Unicode tables."""
import pytest

from mathema_language import words
from mathema_language.text import _algebra
from mathema_language.text.shape import Shape

POSTCODE = Shape("AA99[ ]9AA", "ascii")


def _definition(argument, word, base):
    return words._pattern_language_of(argument, word, base).to_json()["definition"]


def _same_meaning(a, b):
    keys = ("language",) if a["exact"] else ("at_least", "at_most")
    return a["exact"] == b["exact"] and all(
        _algebra.canonical(a[k]) == _algebra.canonical(b[k]) for k in keys)


def test_matches_a_unicode_shape_is_the_shape_s_own_term():
    found = _definition('shape("A9")', "matches", "unicode")
    want = Shape("A9", "unicode").term()
    assert want["exact"] is False
    assert _same_meaning(found, want)


def test_matches_a_named_shape_object_is_its_own_term():
    found = _definition("tests.test_words_shape_argument_term.POSTCODE", "matches", "ascii")
    assert _same_meaning(found, POSTCODE.term())


@pytest.mark.parametrize("word, before, after", [
    ("contains", True, True), ("starts with", False, True), ("ends with", True, False)])
def test_the_other_words_put_any_text_around_the_shape_s_term(word, before, after):
    found = _definition('shape("A9")', word, "unicode")
    shape = Shape("A9", "unicode").term()
    assert found["exact"] is False
    for bound in ("at_least", "at_most"):
        node = found[bound]
        for inner, outer in (("a1", "a1"), ("a1", "xa1"), ("a1", "a1x"), ("a1", "xa1x")):
            holds = _algebra.member({**found, "exact": True, "language": node}, outer)
            assert _algebra.member({**shape, "exact": True, "language": shape[bound]}, inner)
            expect = (before or not outer.startswith("x")) and (after or not outer.endswith("x"))
            assert holds == expect, (word, bound, outer)


def test_membership_still_reads_the_shape():
    language = words._pattern_language_of('shape("AA99[ ]9AA")', "matches", "ascii")
    assert language.contains("SW19 3AB")
    assert not language.contains("SW19 3AB\n")
