# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""An ECMAScript pattern as a regular-language term, held to a JavaScript
engine's recorded verdicts.

`tests/data/javascript_regex_corpus.json` holds what Node said of each
generated (pattern, flags, text) under the four predicates, stamped with
its Node, V8 and Unicode versions (`tests/_javascript_corpus.py` records
it). The term must agree wherever it is exact, hold every string the
engine admits in its at-least bound where it is not, and refuse exactly
the patterns the engine refuses. No engine runs here unless
`MATHEMA_NODE_LIVE` is set, which records again and compares."""
import json
import os

import pytest

from mathema_language.text import _regular as rx
from tests import _javascript_corpus as corpus


def js(pattern, flags="", predicate="matches"):
    return rx.term(pattern, flags, predicate, "javascript")


def test_the_term_agrees_with_the_recorded_engine():
    recorded = json.loads(corpus.CORPUS.read_text())
    assert recorded["node"] and recorded["v8"] and recorded["unicode"]
    exact = bounded = refused = 0
    wrong = []
    for case in recorded["cases"]:
        pattern, flags, texts = case["pattern"], case["flags"], case["texts"]
        if "error" in case:
            refused += 1
            with pytest.raises(rx.NotRegular):
                js(pattern, flags)
            continue
        for predicate in corpus.PREDICATES:
            doc = js(pattern, flags, predicate)
            for text, verdict in zip(texts, case["verdicts"][predicate], strict=True):
                if doc["exact"]:
                    exact += 1
                    if rx.member(doc, text) != verdict:
                        wrong.append((pattern, flags, predicate, text, verdict))
                else:
                    bounded += 1
                    if verdict and not rx.member(doc, text, "at_least"):
                        wrong.append((pattern, flags, predicate, text, verdict))
                    assert doc["at_most"] == {"op": "empty"}
    assert wrong == [], (len(wrong), wrong[:5])
    assert exact > 10000 and bounded > 1000 and refused > 50, (exact, bounded, refused)


def test_the_corpus_is_the_cases_the_recorder_generates():
    recorded = json.loads(corpus.CORPUS.read_text())
    assert [[c["pattern"], c["flags"], c["texts"]] for c in recorded["cases"]] == corpus.cases()


@pytest.mark.skipif(not os.environ.get("MATHEMA_NODE_LIVE"), reason="set MATHEMA_NODE_LIVE")
def test_a_live_engine_still_says_what_was_recorded():
    recorded = json.loads(corpus.CORPUS.read_text())
    live = corpus.record()
    drift = [(a["pattern"], a["flags"]) for a, b in zip(recorded["cases"], live["cases"], strict=True)
             if a != b]
    assert drift == [], (live["node"], live["v8"], recorded["node"], recorded["v8"], drift[:5])


# -- where javascript parts from python ---------------------------------------

def test_dollar_is_the_end_alone_and_a_line_end_under_m():
    assert rx.member(js(r"a$"), "a") and not rx.member(js(r"a$", "", "contains"), "a\n")
    assert rx.member(js(r"a$", "m", "contains"), "a\nb")
    assert rx.member(js(r"a$", "m", "contains"), "a b")
    assert rx.member(js(r"^b", "m", "contains"), "a\rb")


def test_digits_and_words_are_ascii_and_space_is_the_specification_list():
    assert not rx.member(js(r"\d"), "٣") and not rx.member(js(r"\w"), "é")
    assert rx.member(js(r"\s"), "﻿") and not rx.member(js(r"\s"), "\x1c")
    assert not rx.member(js(r"."), " ") and rx.member(js(r".", "s"), " ")


def test_without_u_a_string_is_its_code_units():
    assert js(".")["alphabet"] == [[0, 0xFFFF]] and js(".", "u")["alphabet"] == [[0, 0x10FFFF]]
    assert not rx.member(js("."), "\U0001F600") and rx.member(js(".."), "\U0001F600")
    assert rx.member(js(".", "u"), "\U0001F600")
    assert rx.member(js("\U0001F600+"), "\U0001F600\ude00")
    assert not rx.member(js("\U0001F600+", "u"), "\U0001F600\ude00")


def test_ignore_case_reads_by_canonical_form():
    assert rx.member(js("k", "iu"), "K") and not rx.member(js("k", "i"), "K")
    assert rx.member(js(r"\w", "iu"), "ſ") and not rx.member(js(r"\w", "i"), "ſ")
    assert not rx.member(js("ß", "iu"), "ss") and rx.member(js("ß", "iu"), "ẞ")


def test_sticky_starts_every_match_at_the_start():
    assert not rx.member(js("b", "y", "contains"), "ab") and rx.member(js("b", "", "contains"), "ab")
    assert js("b", "y", "ends with")["language"] == js("b", "y", "matches")["language"]


@pytest.mark.parametrize("pattern, flags, named", [
    (r"(a)\1", "", "a backreference"), (r"(?<n>a)\k<n>", "", "a backreference"),
    (r"(?=a)a", "", "a lookahead"), (r"(?<!a)b", "", "a lookbehind"),
    (r"\p{L}", "u", "a property escape"), (r"[\p{L}\d]", "u", "a property escape"),
    (r"[[a-c]--[b]]", "v", "a class set operation"),
])
def test_what_is_not_regular_is_a_named_bound(pattern, flags, named):
    doc = js(pattern, flags)
    assert not doc["exact"] and doc["source"]["not_exact"] == [named]
    assert doc["at_most"] == {"op": "empty"}


def test_the_source_names_the_dialect_and_its_flags_as_words():
    source = js("a", "gimsuy")["source"]
    assert source["dialect"] == "javascript"
    assert source["flags"] == ["dot all", "global", "ignore case", "multi line", "sticky", "unicode"]
    assert rx.term("a")["source"]["dialect"] == "python"
    with pytest.raises(ValueError, match="dialect"):
        rx.term("a", 0, "matches", "ecma")
    for flags in ("uv", "ii", "x"):
        with pytest.raises(rx.NotRegular):
            js("a", flags)


# -- across dialects, by witness ------------------------------------------------

def _apart(a, b, limit=6):
    """A shortest string in term `a` and not in term `b`, among the strings
    over the characters the two name, or None."""
    return rx.shortest(rx._inter(rx.from_node(a["language"]),
                                 ("not", rx.from_node(b["language"]))), limit)


def test_python_and_javascript_digits_part_at_a_final_newline_and_a_unicode_digit():
    import re
    python, javascript = rx.term(r"^\d+$", 0, "contains"), js(r"^\d+$", "u", "contains")
    for text in ("1\n", "٣"):
        assert re.search(r"^\d+$", text)
        assert rx.member(python, text) and not rx.member(javascript, text)
    witness = _apart(python, javascript)
    assert witness is not None and re.search(r"^\d+$", witness)
    assert rx.member(python, witness) and not rx.member(javascript, witness)
    assert _apart(javascript, python) is None
    assert rx.term_hash(python) != rx.term_hash(javascript)


def test_python_absolute_anchors_are_javascript_plain_ones():
    python, javascript = rx.term(r"\A[a-z]+\Z", 0, "contains"), js(r"^[a-z]+$", "u", "contains")
    assert rx.term_hash(python) == rx.term_hash(javascript)
    assert _apart(python, javascript) is None and _apart(javascript, python) is None
    units = js(r"^[a-z]+$", "", "contains")
    assert units["alphabet"] != python["alphabet"]
    assert _apart(python, units) is None and _apart(units, python) is None
