# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The canonical form and hash of a regular-language term, pinned as data.

`tests/data/regular_term_vectors.json` holds term documents with the
canonical text and SHA-256 each must give, and documents that must be
refused. Another reader of the schema passes when it gives the same
text and hash for every vector."""
import hashlib
import json
from pathlib import Path

import pytest

from mathema_language.text import _regular as rx

VECTORS = json.loads((Path(__file__).parent / "data" / "regular_term_vectors.json").read_text())["vectors"]
VALID = [v for v in VECTORS if not v.get("invalid")]


def test_there_are_enough_vectors_of_each_kind():
    assert len(VALID) >= 40 and len(VECTORS) - len(VALID) >= 10
    assert any(not v["document"]["exact"] for v in VALID)


@pytest.mark.parametrize("vector", VALID, ids=lambda v: v["name"])
def test_a_document_has_its_canonical_text_and_hash(vector):
    text = rx.canonical_text(vector["document"])
    assert text == vector["canonical"]
    assert hashlib.sha256(text.encode("ascii")).hexdigest() == vector["hash"]
    assert rx.term_hash(vector["document"]) == vector["hash"]


@pytest.mark.parametrize("vector", VALID, ids=lambda v: v["name"])
def test_the_canonical_form_is_a_fixed_point_and_keeps_the_language(vector):
    document = vector["document"]
    for key in ("language", "at_least", "at_most"):
        if key not in document:
            continue
        once = rx.canonical(document[key])
        assert rx.canonical(once) == once
        assert rx.canonical(json.loads(json.dumps(once))) == once
        for text in ["", "a", "b", "ab", "abc", "aa", "0", "a0b", "x", "\ud83d" + "\ude00", "\U0001F600"]:
            assert rx.holds(rx.from_node(document[key]), text) == rx.holds(rx.from_node(once), text)


@pytest.mark.parametrize("vector", [v for v in VECTORS if v.get("invalid")], ids=lambda v: v["name"])
def test_a_malformed_document_is_refused(vector):
    with pytest.raises(ValueError):
        rx.term_hash(vector["document"])


def test_a_surrogate_pair_is_not_the_character_it_encodes():
    import re
    pair, one = rx.term(re.escape("\ud83d" + "\ude00")), rx.term("\U0001F600")
    assert rx.term_hash(pair) != rx.term_hash(one)
    back = json.loads(json.dumps(pair, ensure_ascii=True))
    assert rx.member(back, "\ud83d" + "\ude00") and not rx.member(back, "\U0001F600")
    assert back["language"] == pair["language"] and rx.term_hash(back) == rx.term_hash(pair)


def test_equal_documents_spelled_differently_hash_the_same():
    by_text = {}
    for v in VALID:
        by_text.setdefault(v["canonical"], set()).add(v["hash"])
    assert all(len(hashes) == 1 for hashes in by_text.values())
    assert len({v["hash"] for v in VALID}) == len(by_text)
