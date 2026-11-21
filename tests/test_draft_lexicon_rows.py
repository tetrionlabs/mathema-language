# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The draft lexicon rows: one worked claim for each language, predicate
word and constructor the package newly registers. A predicate word's row
is in the canonical spelling, the word as words (an underscore in its key
read as a space) followed by its bracketed argument; with mathema's word
registry installed every row parses and renders back to itself.

The rows are kept apart from the package's lexicon while their names are
drafts: a predicate row does not parse on a mathema without the word
registry, and the lexicon's own tests read every row."""
import importlib.metadata as md
import re

import pytest

pytest.importorskip("mathema")

from mathema_language import words  # noqa: E402

ROWS = words.DRAFT_ROWS


def _entry_points(group):
    dist = md.distribution("mathema-language")
    return {ep.name: ep for ep in dist.entry_points if ep.group == group}


def _predicate_words():
    """The registered predicate words, by entry-point key: an entry that
    loads as a word of the registry, not a measure or a constructor."""
    if not words.WORDS:
        pytest.skip("this mathema has no word registry")
    found = {}
    for key, ep in _entry_points("mathema.language_refinements").items():
        loaded = ep.load()
        if getattr(loaded, "word", None) is not None and loaded in words.WORDS.values():
            found[key] = loaded.word
    return found


def test_every_registered_predicate_word_has_a_row_in_the_canonical_spelling():
    found = _predicate_words()
    assert set(found) == {"matches", "contains", "starts_with", "ends_with", "within", "shape"}
    for key, word in found.items():
        assert word == key.replace("_", " ")
        assert key in ROWS, key
        assert re.search(rf"L\[[^\]]*,\s*{re.escape(word)} \(", ROWS[key]), ROWS[key]


@pytest.mark.parametrize("name", ["lower", "upper"])
def test_each_newly_registered_language_has_a_row(name):
    assert name in _entry_points("mathema.languages")
    assert re.search(rf"L\[{name}[\],]", ROWS[name])


def test_the_alphabet_constructor_has_a_row_headed_by_an_alphabet_expression():
    assert "alphabet" in _entry_points("mathema.language_refinements")
    assert re.search(r"L\[\w+(?: \+ (?:\w+|\"[^\"]\"))+[\],]", ROWS["alphabet"])


def test_there_is_a_row_for_every_new_entry_point_and_no_other():
    assert set(ROWS) == {"lower", "upper", "matches", "contains", "starts_with", "ends_with",
                         "within", "shape", "alphabet"}


@pytest.mark.parametrize("key", sorted(words.DRAFT_ROWS))
def test_a_row_parses_and_renders_back_to_itself(key):
    if not words.WORDS and key not in ("lower", "upper"):
        pytest.skip("this mathema has no word registry")
    from mathema.conjecture import claim
    from mathema.spec import render_claim_text
    assert render_claim_text(claim(ROWS[key]), unicode=False) == ROWS[key]
