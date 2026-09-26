# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Every text language satisfies mathema's protocol, its hazards and
samples are members, its outside draws never are, it explains a
refusal by naming the offending character, it shrinks only to members,
and its persisted form names it."""
import random

import pytest

from mathema_language._surface import HAZARD_KINDS, language_problems
from mathema_language.text import LANGUAGES
from mathema_language.text.alphabets import (
    ALNUM,
    ALPHA,
    ASCII,
    C0,
    COMBINING,
    DIGIT,
    FORMAT,
    LATIN1,
    NFKC_FOLDING,
    NON_BMP,
    PRINTABLE,
    SURROGATE,
    UNICODE,
)

ALPHABETS = [UNICODE, ASCII, LATIN1, PRINTABLE, DIGIT, ALPHA, ALNUM,
             C0, FORMAT, COMBINING, SURROGATE, NFKC_FOLDING, NON_BMP]


@pytest.mark.parametrize("language", list(LANGUAGES.values()), ids=lambda lang: lang.name)
def test_satisfies_the_protocol(language):
    assert language_problems(language) == []
    assert LANGUAGES[language.name] is language


@pytest.mark.parametrize("language", list(LANGUAGES.values()), ids=lambda lang: lang.name)
def test_hazards_are_members_with_known_kinds(language):
    hazards = language.hazards()
    assert hazards, language.name
    for hazard in hazards:
        assert hazard.kind in HAZARD_KINDS, hazard
        assert language.contains(hazard.value), (language.name, hazard)
    assert len({h.value for h in hazards}) == len(hazards)


@pytest.mark.parametrize("language", list(LANGUAGES.values()), ids=lambda lang: lang.name)
def test_samples_are_members(language):
    rng = random.Random(7)
    for _ in range(200):
        value = language.sample(rng)
        assert isinstance(value, str)
        assert language.contains(value), (language.name, value)


@pytest.mark.parametrize("language", list(LANGUAGES.values()), ids=lambda lang: lang.name)
def test_outside_is_never_a_member(language):
    rng = random.Random(7)
    for _ in range(50):
        value = language.outside(rng)
        assert value is None or not language.contains(value), (language.name, value)


@pytest.mark.parametrize("language", list(LANGUAGES.values()), ids=lambda lang: lang.name)
def test_shrink_offers_members_only(language):
    rng = random.Random(3)
    value = language.sample(rng)
    for smaller in language.shrink(value):
        assert language.contains(smaller), (language.name, value, smaller)
        assert len(smaller) <= len(value)


@pytest.mark.parametrize("language", list(LANGUAGES.values()), ids=lambda lang: lang.name)
def test_the_persisted_form_names_the_language(language):
    form = language.to_json()
    assert form["type"] == "string" and form["language"] == language.name


@pytest.mark.parametrize("language", ALPHABETS, ids=lambda lang: lang.name)
def test_an_alphabet_contains_the_empty_string(language):
    assert language.contains("")
    assert language.level == "alphabet"


def test_ascii_and_latin1_boundaries():
    assert ASCII.contains("abc\x00\x7f") and not ASCII.contains("\x80")
    assert LATIN1.contains("\x80\xff") and not LATIN1.contains("\u0100")
    assert UNICODE.contains("\ud800") and UNICODE.outside(random.Random(1)) is None


def test_digit_is_the_ten_ascii_digits():
    assert DIGIT.contains("0123456789")
    assert not DIGIT.contains("\u0663") and not DIGIT.contains("\u00b2")


def test_the_hazard_sub_alphabets_are_what_they_say():
    assert C0.contains("\x00\x1f ") and not C0.contains("a")
    assert FORMAT.contains("\u200b\ufeff\u202e") and not FORMAT.contains("a")
    assert COMBINING.contains("\u0301\u0308") and not COMBINING.contains("e")
    assert SURROGATE.contains("\ud800\udfff") and not SURROGATE.contains("a")
    assert NFKC_FOLDING.contains("\ufb01\u2100") and not NFKC_FOLDING.contains("a")
    assert NON_BMP.contains("\U0001f642") and not NON_BMP.contains("\uffff")


def test_explain_names_the_offending_character():
    problem, = ASCII.explain("ab\u00e9")
    assert problem.path == "[2]" and problem.value == "\u00e9"
    assert ASCII.explain("abc") is None
    assert ASCII.explain(3)[0].predicate == "str"


def test_shrinking_prefers_the_simplest_character():
    smaller = DIGIT.shrink("789")
    assert "089" in smaller and "" in smaller
    assert all(DIGIT.contains(s) for s in smaller)


def test_sampling_reaches_the_astral_planes_for_unicode():
    rng = random.Random(11)
    seen_astral = any(any(ord(c) > 0xFFFF for c in UNICODE.sample(rng))
                      for _ in range(300))
    assert seen_astral


def test_a_language_s_hazards_include_the_text_corpus_where_it_applies():
    values = {h.value for h in UNICODE.hazards()}
    assert "\ud800" in values and "\ufeff" in values and "\u00df" in values
    ascii_values = {h.value for h in ASCII.hazards()}
    assert "\x00" in ascii_values and "\u00df" not in ascii_values
    assert any(h.kind == "length" for h in DIGIT.hazards())
