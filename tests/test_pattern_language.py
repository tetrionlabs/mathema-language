# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The language of a Python pattern under a predicate, and the terms the
alphabet languages state.

`pattern_language` builds the language from a compiled pattern, a
pattern's text, or a compiled pattern's `fullmatch`, `search` or `match`
method: membership is `re` itself, its definition is the term, its
draws are members. A bare compiled pattern is not a language by itself:
the text adaptor does not read one. Each alphabet language states the
term of every string over its characters, and a length bound refines
it."""
import json
import random
import re

import pytest

from mathema_language._surface import language_problems
from mathema_language.refinements import length, length_bound
from mathema_language.text import LANGUAGES, UNICODE, adapt, pattern_language
from mathema_language.text import _regular as rx

SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def test_the_text_adaptor_does_not_read_a_bare_pattern():
    assert adapt(SLUG) is None and adapt(SLUG.fullmatch) is None


def test_a_compiled_pattern_reads_as_matches():
    lang = pattern_language(SLUG)
    assert lang.contains("a-b1") and not lang.contains("a-") and not lang.contains("a-b\n")
    assert not lang.contains(3) and language_problems(lang) == []
    assert lang.to_json()["definition"] == rx.term(SLUG, 0, "matches")


@pytest.mark.parametrize("method, predicate, inside, outside", [
    ("fullmatch", "matches", "ab", "ab\n"), ("search", "contains", "1ab\n", "1"),
    ("match", "starts with", "ab\n", "1ab"),
])
def test_a_bound_method_names_its_predicate(method, predicate, inside, outside):
    compiled = re.compile(r"[a-z]+$", re.I)
    lang = pattern_language(getattr(compiled, method))
    doc = lang.to_json()["definition"]
    assert doc["source"]["predicate"] == predicate and doc["source"]["flags"] == ["ignore case"]
    assert lang.contains(inside) and not lang.contains(outside)
    for text in [inside, outside, "", "AB", "ab\n\n"]:
        assert rx.member(doc, text) == lang.contains(text)
    with pytest.raises(ValueError, match="reads as"):
        pattern_language(getattr(compiled, method), "ends with")
    with pytest.raises(ValueError):
        pattern_language(compiled.sub)


@pytest.mark.parametrize("predicate", list(rx.PREDICATES))
def test_pattern_text_and_flags_under_each_predicate(predicate):
    lang = pattern_language(r"^b$", predicate, re.M)
    doc = lang.to_json()["definition"]
    assert doc == rx.term(r"^b$", re.M, predicate)
    json.dumps(lang.to_json(), ensure_ascii=True)
    for text in ["b", "a\nb", "b\na", "a\nb\nc", "ab", "", "b\n"]:
        assert lang.contains(text) == rx.runs(r"^b$", re.M, predicate, text) == rx.member(doc, text)


def test_draws_are_members():
    for source, predicate in [(SLUG, None), (re.compile(r"\d{3}-\d{4}").search, None),
                              (r"(?i)colou?r", "starts with"), (r"a$", "ends with")]:
        lang = pattern_language(source, predicate)
        rng = random.Random(0)
        for _ in range(20):
            assert lang.contains(lang.sample(rng))


def test_a_pattern_that_is_not_regular_states_its_bounds():
    lang = pattern_language(re.compile(r"(a+)\1"))
    doc = lang.to_json()["definition"]
    assert not doc["exact"] and doc["source"]["not_exact"] == ["a backreference"]
    assert lang.contains("aa") and not lang.contains("aaa")


def test_a_bytes_pattern_is_refused():
    with pytest.raises(rx.NotRegular):
        pattern_language(re.compile(rb"a"))


# -- the alphabet languages ----------------------------------------------------

ALPHABETS = [name for name, lang in LANGUAGES.items() if lang.level == "alphabet"]


def test_every_alphabet_language_is_covered():
    assert {"unicode", "ascii", "latin-1", "printable", "digit", "alpha", "alnum", "unicode_alpha",
            "unicode_alnum", "control", "invisible", "combining", "surrogate", "compatibility",
            "astral"} <= set(ALPHABETS)


@pytest.mark.parametrize("name", ALPHABETS)
def test_an_alphabet_states_every_string_over_its_characters(name):
    lang = LANGUAGES[name]
    doc = lang.to_json()["definition"]
    assert doc["exact"] and doc["alphabet"] == [[0, 0x10FFFF]] and doc["kind"] == "regular_language"
    node = doc["language"]
    assert node["op"] == "repeat" and node["min"] == 0 and node["max"] is None
    arg = node["arg"]
    spans = arg["ranges"] if arg["op"] == "chars" else [[c, c] for c in arg["codes"]]
    stated = {c for lo, hi in spans for c in range(lo, hi + 1)}
    assert stated == {c for c in range(0x110000) if lang.contains(chr(c))}
    rng = random.Random(1)
    texts = ["", "a", "0", "a0", "\x00", "\u00e9", "\u200b", "\ud800", "\U0001F600", "a b", "\u0301"]
    texts += [lang.sample(rng) for _ in range(20)]
    for text in texts:
        assert rx.member(doc, text) == lang.contains(text), (name, text)
    json.dumps(lang.to_json(), ensure_ascii=True)


@pytest.mark.parametrize("name, lo, hi", [("digit", 1, 3), ("unicode", 0, 2), ("ascii", 2, None),
                                          ("alnum", 0, 0), ("unicode_alpha", 1, 2)])
def test_a_length_bound_refines_the_definition(name, lo, hi):
    refined = length(LANGUAGES[name], length_bound(lo, hi))
    doc = refined.to_json()["definition"]
    assert doc["exact"] and doc["language"].get("min", 0) == lo
    for text in ["", "1", "12", "123", "1234", "a", "ab", "abc", "a1", "\u00e9", "\U0001F600\U0001F600", " "]:
        assert rx.member(doc, text) == refined.contains(text), (name, text)
    assert rx.term_hash(doc) != rx.term_hash(LANGUAGES[name].to_json()["definition"]) or (lo, hi) == (0, None)


def test_a_length_bound_over_a_pattern_language_meets_its_term():
    refined = length(pattern_language(r"a+b?"), length_bound(2, 3))
    doc = refined.to_json()["definition"]
    for text in ["a", "aa", "ab", "aab", "aaab", "aaa", "b", ""]:
        assert rx.member(doc, text) == refined.contains(text)


def test_unicode_is_every_string():
    assert UNICODE.to_json()["definition"]["language"] == rx._EVERY_STRING
