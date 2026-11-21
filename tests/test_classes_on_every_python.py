# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Shapes, alphabets and readings take their Unicode classes from the
version table: a term without a version is the same on every supported
Python, a pair of bounds where a class differs between versions and
exact over ASCII; a term with a version is that Python's, exact."""
import json

import pytest

from mathema_language.text import _regular as rx
from mathema_language.text.alphabet import alphabet, alphabet_language
from mathema_language.text.explain import explain
from mathema_language.text.shape import Shape

VERSIONS = rx.versions_data()["versions"]
NEW_LETTER = "\U00010570"       # a letter from Unicode 14.0: Python 3.11 and later
UNASSIGNED = chr(rx.versions_data()["unassigned"][0][0])


@pytest.mark.parametrize("expression, exact", [
    ("unicode_alpha", False), ("unicode_alnum + \"_\"", False), ("printable", False),
    ("unicode_alpha + digit", False), ("alnum", True), ("lower + digit + \"-\"", True),
    ("hex", True), ("ascii", True), ("unicode", True), ("latin-1", True),
])
def test_an_alphabet_language_states_one_definition_for_every_python(expression, exact):
    language = alphabet_language(expression)
    doc = language.to_json()["definition"]
    assert doc["exact"] is exact and json.loads(json.dumps(doc)) == doc
    assert doc["source"]["versions"] == VERSIONS
    if exact:
        return
    assert doc["source"]["not_exact"] and all(
        why.endswith("between Python versions") for why in doc["source"]["not_exact"])
    low, high = alphabet(expression).bounds
    for text in ["a", "é", "中", "", "aé"]:
        assert rx.member(doc, text, "at_most") and language.contains(text)
    assert rx.member(doc, NEW_LETTER, "at_least") and not rx.member(doc, NEW_LETTER, "at_most")
    assert rx.member(doc, UNASSIGNED, "at_least") and not rx.member(doc, UNASSIGNED, "at_most")
    assert set(low) != set(high)


def test_an_alphabet_pinned_to_a_version_is_that_python_reading():
    language = alphabet_language("unicode_alpha")
    old, new = language.definition(version="3.10"), language.definition(version="3.14")
    assert old["exact"] and new["exact"] and old["source"]["versions"] == ["3.10"]
    assert rx.member(new, NEW_LETTER) and not rx.member(old, NEW_LETTER)
    assert rx.term_hash(old) != rx.term_hash(new)
    with pytest.raises(ValueError, match="supported"):
        language.definition(version="3.9")


@pytest.mark.parametrize("written, base, exact", [
    ("AA99", "unicode", False), ("a{1+}", "unicode", False), ("9{2}", "unicode", False),
    ("X{0+}", "unicode", True), ("'ID-'X", "unicode", True), ("AA99", "ascii", True),
    ("a{1+}[-9]", "ascii", True),
])
def test_a_shape_states_one_term_for_every_python(written, base, exact):
    doc = Shape(written, base).term()
    assert doc["exact"] is exact and json.loads(json.dumps(doc)) == doc
    if not exact:
        assert doc["source"]["versions"] == VERSIONS
        assert all(why.endswith("between Python versions") for why in doc["source"]["not_exact"])


def test_a_shape_bounds_hold_what_every_python_and_any_python_reads():
    shape = Shape("A9")
    doc = shape.term()
    assert doc["source"]["not_exact"] == ["digits, which differ slightly between Python versions",
                                          "letters, which differ slightly between Python versions"]
    assert rx.member(doc, "a1", "at_most") and rx.member(doc, "é٣", "at_most")
    assert rx.member(doc, NEW_LETTER + "1", "at_least") and not rx.member(doc, NEW_LETTER + "1", "at_most")
    assert not rx.member(doc, "1a", "at_least")
    old, new = shape.term(version="3.10"), shape.term(version="3.14")
    assert old["exact"] and new["exact"]
    assert rx.member(new, NEW_LETTER + "1") and not rx.member(old, NEW_LETTER + "1")


def test_a_bound_symbol_takes_its_alphabet_bounds():
    assert Shape("WW", "unicode", W="unicode_alnum").term()["exact"] is False
    assert Shape("WW", "unicode", W="alnum").term()["exact"] is True
    assert Shape("WW", "ascii", W="hex").term()["exact"] is True


def test_a_reading_says_a_bound_in_words():
    said = explain(Shape("A{1+}").term())
    assert said == (
        "approximate because it holds letters, which differ slightly between Python versions; "
        "every accepted text fits: one or more of: letters (Unicode, every character a supported "
        "Python holds or may come to); not every text that fits is accepted; certainly accepted: "
        f"one or more of: letters (Unicode, {_size('unicode_alpha')} characters)")
    assert Shape("AA99", "ascii").explain() == "exactly 2 of: ASCII letters; then exactly 2 of: 0-9"
    assert "approximate because it holds letters and digits, which differ slightly between Python versions" \
        in explain(alphabet_language("unicode_alnum").to_json()["definition"])


def _size(name):
    low, _ = rx.class_bounds(name)
    return sum(hi - lo + 1 for lo, hi in low)


def test_the_terms_are_built_from_the_table_alone():
    # no class of an unpinned term is read from the running interpreter: each set in the
    # bounds is one the table states
    doc = Shape("Aa9").term()
    stated = set()
    for name in ("unicode_alpha", "lowercase_letter", "decimal"):
        low, high = rx.class_bounds(name)
        stated |= {tuple(map(tuple, low)), tuple(map(tuple, high))}
    for bound in ("at_least", "at_most"):
        for arg in doc[bound]["args"]:
            assert tuple(tuple(r) for r in arg["ranges"]) in stated
