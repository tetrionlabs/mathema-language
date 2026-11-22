# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""What a regular-language document must state to be read, and how its
alphabet bounds its language: a text with a character outside the
alphabet is no member, whatever the node admits."""
import pytest

from mathema_language.text import _regular as rx

FULL = [[0, 0x10FFFF]]
NOT_A = {"op": "complement", "arg": {"op": "literal", "codes": [97]}}


def exact(language, alphabet=None):
    return {"kind": "regular_language", "version": 1, "alphabet": alphabet or FULL, "exact": True,
            "language": language, "source": {}}


def pair(at_least, at_most, alphabet=None):
    return {"kind": "regular_language", "version": 1, "alphabet": alphabet or FULL, "exact": False,
            "at_least": at_least, "at_most": at_most, "source": {}}


def without(doc, key):
    return {k: v for k, v in doc.items() if k != key}


MALFORMED = {
    "the version is true": {**exact(NOT_A), "version": True},
    "the version is text": {**exact(NOT_A), "version": "1"},
    "no version": without(exact(NOT_A), "version"),
    "no alphabet": without(exact(NOT_A), "alphabet"),
    "no exact flag": without(exact(NOT_A), "exact"),
    "exact is 1": {**exact(NOT_A), "exact": 1},
    "exact is 0": {**pair(NOT_A, NOT_A), "exact": 0},
    "exact with only the bounds": {**pair(NOT_A, NOT_A), "exact": True},
    "not exact with only a language": {**exact(NOT_A), "exact": False},
    "not exact with one bound": without(pair(NOT_A, NOT_A), "at_most"),
    "not an object": [exact(NOT_A)],
}


@pytest.mark.parametrize("name", sorted(MALFORMED))
def test_a_malformed_document_is_refused_with_a_value_error(name):
    for read in (rx.canonical_text, rx.term_hash):
        with pytest.raises(ValueError):
            read(MALFORMED[name])


def test_a_text_with_a_character_outside_the_alphabet_is_no_member():
    lower = [[97, 122]]
    doc = exact(NOT_A, lower)
    assert rx.member(doc, "b") and rx.member(doc, "") and rx.member(doc, "ab")
    assert not rx.member(doc, "a")
    assert not rx.member(doc, "!") and not rx.member(doc, "b!") and not rx.member(doc, "\n")
    assert rx.member(exact(NOT_A), "!")


def test_the_alphabet_bounds_each_bound_of_a_pair():
    doc = pair(NOT_A, {"op": "literal", "codes": [98]}, [[97, 122]])
    assert rx.member(doc, "zz", "at_least") and not rx.member(doc, "Z", "at_least")
    assert rx.member(doc, "b", "at_most") and not rx.member(doc, "B", "at_most")


def test_every_term_this_package_compiles_is_over_all_of_unicode():
    from mathema_language.text import LANGUAGES, regex_language
    docs = [lang.to_json().get("term") for lang in LANGUAGES.values()]
    docs += [rx.term(r"[a-z]+\d", 0, p) for p in rx.PREDICATES]
    docs += [regex_language(r"\w+").to_json()["term"]]
    assert [d["alphabet"] for d in docs if d is not None] == [FULL] * sum(d is not None for d in docs)
