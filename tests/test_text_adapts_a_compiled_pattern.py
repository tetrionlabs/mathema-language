# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The text adaptor reads a compiled pattern as the language of the
strings it matches in full: membership is `re` itself, the definition
it states is the pattern's regular-language term, and its draws are
members."""
import json
import random
import re

from mathema_language._surface import language_problems
from mathema_language.text import _regular as rx
from mathema_language.text import adapt

SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def test_a_compiled_pattern_is_the_language_it_matches_in_full():
    lang = adapt(SLUG)
    assert lang.contains("a-b1") and not lang.contains("a-") and not lang.contains("A")
    assert not lang.contains("a-b\n") and not lang.contains(3)
    assert language_problems(lang) == []


def test_its_definition_is_the_term_of_matches():
    lang = adapt(re.compile(r"[a-z]+$", re.I))
    doc = lang.to_json()["definition"]
    assert doc == rx.term(re.compile(r"[a-z]+$", re.I), 0, "matches")
    assert doc["source"]["flags"] == ["ignore case"] and doc["exact"]
    json.dumps(lang.to_json(), ensure_ascii=True)
    for text in ["abc", "ABC", "abc\n", "", "a1"]:
        assert rx.member(doc, text) == lang.contains(text)


def test_draws_are_members():
    for pattern in (SLUG, re.compile(r"\d{3}-\d{4}"), re.compile(r"(?i)colou?r")):
        lang = adapt(pattern)
        rng = random.Random(0)
        for _ in range(20):
            assert lang.contains(lang.sample(rng))


def test_a_pattern_that_is_not_regular_states_its_bounds():
    lang = adapt(re.compile(r"(a+)\1"))
    doc = lang.to_json()["definition"]
    assert not doc["exact"] and doc["source"]["not_exact"] == ["a backreference"]
    assert lang.contains("aa") and not lang.contains("aaa")


def test_a_bytes_pattern_is_not_a_text_language():
    assert adapt(re.compile(rb"a")) is None
