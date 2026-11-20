# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A Python pattern under a predicate as a regular-language term, held to `re`.

The term is plain data with no solver in it; its membership is decided
here by derivatives and compared with `re` run on the same string, for
hand-picked and generated patterns, every predicate, and strings over
all of Unicode. An exact term must agree with `re`; a term that is not
exact must hold every string `re` admits in its `at_least` bound and
none in its `at_most` bound that `re` refuses."""
import json
import os
import random
import re
import sys

import pytest

from mathema_language.text import _regular as rx

PREDICATES = tuple(rx.PREDICATES)


def runs(pattern, flags, predicate, text):
    """What `re` says: the reading each predicate names."""
    compiled = re.compile(pattern, flags)
    if predicate == "matches":
        return compiled.fullmatch(text) is not None
    if predicate == "contains":
        return compiled.search(text) is not None
    if predicate == "starts with":
        return compiled.match(text) is not None
    return any(compiled.fullmatch(text, i) is not None for i in range(len(text) + 1))


def disagreements(pattern, flags, texts, predicates=PREDICATES):
    """Each (version, predicate, text) where a term parts from `re` run here:
    the term for every supported Python, and the term pinned to this one.
    An exact term must equal `re`; a pair must hold every string `re`
    admits in `at_least` and none `re` refuses in `at_most`."""
    out = []
    for version in (None, rx.RUNNING):
        for predicate in predicates:
            try:
                doc = rx.term(pattern, flags, predicate, version=version)
            except rx.NotRegular:
                if version is None:
                    continue
                raise
            for text in texts:
                expected = runs(pattern, flags, predicate, text)
                if doc["exact"]:
                    if rx.member(doc, text) != expected:
                        out.append((version, predicate, text, expected))
                elif (expected and not rx.member(doc, text, "at_least")) or \
                        (rx.member(doc, text, "at_most") and not expected):
                    out.append((version, predicate, text, expected))
    return out


ANCHOR_TEXTS = ["", "a", "a\n", "a\n\n", "\na", "ab", "b\na", "a\nb", "\n", "aa", "ba", "bab"]


@pytest.mark.parametrize("pattern", [r"a$", r"a\Z", r"^a", r"\Aa", r"\Aa\Z", r"^a$", r"a$\n",
                                     r"$", r"\Z", r"^", r"a$$", r"(?:a$|b)", r"a(?:$|b)",
                                     r"$\n?", r"(^|b)a", r"a\Z\n?", r"\n$", r"^$", r"b^a"])
@pytest.mark.parametrize("flags", [0, re.M])
def test_anchors_under_every_predicate(pattern, flags):
    assert disagreements(pattern, flags, ANCHOR_TEXTS) == []
    assert rx.term(pattern, flags)["exact"]


def test_dollar_admits_one_final_newline_and_end_of_string_admits_none():
    assert rx.member(rx.term(r"a$", 0, "matches"), "a") and not rx.member(rx.term(r"a$"), "a\n")
    assert rx.member(rx.term(r"\Aa$", 0, "contains"), "a\n")
    assert not rx.member(rx.term(r"\Aa\Z", 0, "contains"), "a\n")
    assert not rx.member(rx.term(r"\Aa$", 0, "contains"), "a\n\n")


FLAG_TEXTS = ["a", "A", "\n", "k", "K", "K", "s", "S", "ſ", "İ", "i", "I",
              "ı", "ß", "ss", "ẞ", "σ", "ς", "Σ", "é", "É",
              "", "ab", "aB", "x\ny", "\U00010400", "\U00010428"]


@pytest.mark.parametrize("pattern, flags", [
    ("a", re.I), ("k", re.I), ("s", re.I), ("i", re.I), ("ß", re.I), ("σ", re.I),
    ("[a-z]", re.I), ("[^a-z]", re.I), ("[k-s]", re.I), (r"[à-ÿ]", re.I),
    ("\U00010400", re.I), ("k", re.I | re.A), ("[a-z]", re.I | re.A), ("(?i)k", 0),
    ("(?i:k)b", 0), ("(?i)a(?-i:b)", 0), (".", 0), (".", re.S), ("(?s:.)y", 0), ("x.y", 0),
    ("(?m)^y", 0), (" a  b # comment", re.X), ("(?x) a b", 0),
])
def test_flags_under_every_predicate(pattern, flags):
    assert disagreements(pattern, flags, FLAG_TEXTS) == []


CLASS_TEXTS = ["0", "9", "٣", "๓", "²", "a", "Z", "_", "é", "一", " ",
               "\t", " ", " ", "\x1c", "　", "-", "\n", "Ⅷ", "½", "",
               "\U00030000", "\U000E0001", "\U0001D7CE", "a b", "ab", " a", "a ", "éa", "0a",
               "\ud800"]


@pytest.mark.parametrize("pattern", [r"\d", r"\w", r"\s", r"\D", r"\W", r"\S", r"[\d\s]", r"[^\w]",
                                     r"[^\W\d]", r"[\w-]", r"\b\w+\b", r"a\b", r"\B", r"\Ba", r"\b",
                                     r"\w+"])
@pytest.mark.parametrize("flags", [0, re.A])
def test_classes_and_boundaries_over_all_of_unicode(pattern, flags):
    assert disagreements(pattern, flags, CLASS_TEXTS) == []


@pytest.mark.parametrize("pattern, defined", [
    (r"\d", str.isdecimal),
    (r"\w", lambda c: c.isalnum() or c == "_"),
    (r"\s", str.isspace),
])
def test_unicode_classes_are_the_unicode_database(pattern, defined):
    expected = {cp for cp in range(0x110000) if defined(chr(cp))}
    got = {c for lo, hi in rx._class_chars(pattern, 0) for c in range(lo, hi + 1)}
    assert got == expected


@pytest.mark.parametrize("pattern", [r"a*?", r"a+?b", r"a{2,3}?", r"a??b", r"(?:ab|a)*c",
                                     r"(a|)b", r"a||b", r"((a)(b(c)?))+", r"a{0}", r"a{3}",
                                     r"(?:a{2}){2,}", r"[\x41-\x43]+", r"é\x0a",
                                     r"(?:a|b?)+c", r"(?:)*", r"(?:a*)*b"])
def test_repeats_groups_and_escapes(pattern):
    texts = ["", "a", "aa", "aaa", "aaaa", "b", "ab", "aab", "abc", "c", "abab", "ababc",
             "aac", "A", "C", "AB", "é\n", "bc"]
    assert disagreements(pattern, 0, texts) == []
    assert rx.term(pattern, 0)["exact"]


def test_a_large_bound_is_kept_as_a_count():
    texts = ["a" * 999, "a" * 1000, "a" * 1001, "ab" * 200, "ab" * 200 + "c"]
    for pattern in (r"a{1000}", r"[ab]{2,4000}"):
        assert disagreements(pattern, 0, texts, ("matches", "starts with")) == []
    node = rx.term(r"a{1000}")["language"]
    assert node == {"op": "repeat", "arg": {"op": "literal", "codes": [97]}, "min": 1000, "max": 1000}


@pytest.mark.parametrize("pattern, named", [
    (r"(a)\1", "a backreference"), (r"(?=a)a", "a lookahead"), (r"(?!a)b", "a lookahead"),
    (r"(?<=a)b", "a lookbehind"), (r"(?<!a)b", "a lookbehind"),
    (r"(a)?(?(1)b|c)", "a conditional group"), (r"(?>a+)a", "an atomic group"),
    (r"a*+a", "a possessive repeat"), (r"(?:\ba)*", "inside an unbounded repeat"),
])
def test_what_is_not_regular_is_a_named_bound(pattern, named):
    texts = ["", "a", "aa", "aaa", "b", "ab", "ba", "c", "bc", "abc", " a", "a a"]
    if sys.version_info < (3, 11) and named in ("an atomic group", "a possessive repeat"):
        # Python 3.10 reads neither: the pattern does not compile there
        with pytest.raises(rx.NotRegular, match="does not compile on this Python"):
            rx.term(pattern, 0, "matches", version=rx.RUNNING)
        return
    for predicate in PREDICATES:
        doc = rx.term(pattern, 0, predicate, version=rx.RUNNING)
        assert not doc["exact"] and "language" not in doc
        assert any(named in why for why in doc["source"]["not_exact"])
    assert disagreements(pattern, 0, texts) == []


def test_what_does_not_compile_is_refused():
    for pattern in ("[a", "a{2,1}", b"a"):
        with pytest.raises(rx.NotRegular):
            rx.term(pattern)
    with pytest.raises(ValueError, match="predicate"):
        rx.term("a", 0, "fullmatch")


# -- the term as data ----------------------------------------------------------

def _nodes(node):
    yield node
    for child in node.get("args", []):
        yield from _nodes(child)
    if "arg" in node:
        yield from _nodes(node["arg"])


@pytest.mark.parametrize("pattern, flags", [(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", 0), (r"\b\w+\b", 0),
                                            (r"(?i)colou?r", 0), (r"a$", re.M), (r"(a)\1", 0)])
def test_a_term_is_canonical_plain_data(pattern, flags):
    doc = rx.term(pattern, flags, "contains")
    text = json.dumps(doc, sort_keys=True, ensure_ascii=True)
    assert json.loads(text) == doc
    assert doc["kind"] == "regular_language" and doc["version"] == rx.TERM_VERSION
    assert doc["alphabet"] == [[0, 0x10FFFF]]
    assert doc["source"]["dialect"] == "python" and doc["source"]["pattern"] == pattern
    ops = {"empty", "epsilon", "literal", "chars", "concat", "union", "inter", "complement",
           "repeat"}
    for key in ("language", "at_least", "at_most"):
        for node in _nodes(doc.get(key, {"op": "empty"})):
            assert node["op"] in ops
            if node["op"] in ("concat", "union", "inter"):
                assert len(node["args"]) >= 2
                assert all(a["op"] != node["op"] for a in node["args"])
            if node["op"] == "concat":
                assert all(a["op"] not in ("epsilon", "empty") for a in node["args"])
            if node["op"] == "chars":
                spans = node["ranges"]
                assert all(lo <= hi for lo, hi in spans)
                assert all(a[1] + 1 < b[0] for a, b in zip(spans, spans[1:], strict=False))


def test_flags_are_named_as_words_sorted():
    assert rx.term("(?i)a", re.M)["source"]["flags"] == ["ignore case", "multi line"]
    assert rx.term("a", re.S | re.A | re.X)["source"]["flags"] == ["ascii only", "dot all", "verbose"]
    assert rx.term("a")["source"]["flags"] == []


def test_the_hash_reads_the_meaning_not_the_source():
    a, b = rx.term(r"a$", 0, "matches"), rx.term(r"(?:a)\Z", 0, "matches")
    assert a["source"] != b["source"]
    assert rx.term_hash(a) == rx.term_hash(b)
    moved = dict(a, source={**a["source"], "python": "0.0.0"})
    assert rx.term_hash(moved) == rx.term_hash(a)
    assert rx.term_hash(rx.term(r"a$", 0, "contains")) != rx.term_hash(a)
    split = {**a, "language": {"op": "concat", "args": [{"op": "literal", "codes": [97]},
                                                         {"op": "epsilon"}]}}
    assert rx.term_hash(split) == rx.term_hash(a)


def test_a_term_round_trips_through_its_nodes():
    for pattern in [r"\Aa\Z", r"[^\n]+$", r"(?:ab|c){2,5}", r"\b\d"]:
        doc = rx.term(pattern, 0, "contains", version=rx.RUNNING)
        node = rx.to_node(rx.from_node(doc["language"]))
        assert node == doc["language"]


def test_complement_and_intersection_are_read():
    letters = {"op": "repeat", "arg": {"op": "chars", "ranges": [[97, 122]]}, "min": 1, "max": None}
    no_x = {"op": "complement", "arg": {"op": "concat", "args": [
        {"op": "repeat", "arg": {"op": "chars", "ranges": [[0, 0x10FFFF]]}, "min": 0, "max": None},
        {"op": "literal", "codes": [120]},
        {"op": "repeat", "arg": {"op": "chars", "ranges": [[0, 0x10FFFF]]}, "min": 0, "max": None}]}}
    doc = {"language": {"op": "inter", "args": [letters, no_x]}}
    assert rx.member(doc, "abc") and not rx.member(doc, "axc") and not rx.member(doc, "")


# -- differential --------------------------------------------------------------

ALPHABET = ["a", "b", "A", "\n", " ", "1", "٣", "_", "é", "K", "k", "-",
            "\U00030000", "\U000E0001"]
ATOMS = ["a", "b", "k", ".", "[ab]", "[^a]", r"\d", r"\w", r"\s", r"\W", "[a-c]", r"\n", "-",
         "^", "$", r"\A", r"\Z", r"\b", r"\B", "", "[^\\n]", "(?=a)", "(?!b)", "(?<=a)",
         "(?<!b)"]


def _generate(rng, depth=0):
    roll = rng.random()
    if depth > 2 or roll < 0.35:
        return rng.choice(ATOMS)
    if roll < 0.6:
        return _generate(rng, depth + 1) + _generate(rng, depth + 1)
    if roll < 0.75:
        return "(?:" + _generate(rng, depth + 1) + "|" + _generate(rng, depth + 1) + ")"
    sub = _generate(rng, depth + 1)
    quant = rng.choice(["*", "+", "?", "{2}", "{1,3}", "{0,2}", "*?", "+?", "??", "*+", "++"])
    return "(" + sub + ")" + quant


def _texts(rng, n):
    out = {"", "\n"}
    while len(out) < n:
        out.add("".join(rng.choice(ALPHABET) for _ in range(rng.randint(1, 6))))
    return sorted(out)


def _sweep(n_patterns, n_texts, seed):
    rng = random.Random(seed)
    exact = inexact = checks = 0
    wrong = []
    for _ in range(n_patterns):
        pattern = _generate(rng)
        flags = rng.choice([0, re.I, re.M, re.S, re.A, re.I | re.M, re.I | re.A])
        try:
            rx.term(pattern, flags, version=rx.RUNNING)
        except rx.NotRegular:
            continue
        if rx.term(pattern, flags, version=rx.RUNNING)["exact"]:
            exact += 1
        else:
            inexact += 1
        texts = _texts(rng, n_texts)
        checks += 2 * len(texts) * len(PREDICATES)
        wrong += [(pattern, flags, *d) for d in disagreements(pattern, flags, texts)]
    return exact, inexact, checks, wrong


def test_generated_patterns_agree_with_re():
    exact, inexact, checks, wrong = _sweep(150, 25, seed=20261119)
    assert exact >= 80 and inexact >= 10 and wrong == [], (exact, inexact, checks, wrong[:5])


@pytest.mark.skipif(not os.environ.get("MATHEMA_REGEX_SWEEP"), reason="set MATHEMA_REGEX_SWEEP")
def test_a_large_sweep_agrees_with_re():
    exact, inexact, checks, wrong = _sweep(int(os.environ["MATHEMA_REGEX_SWEEP"]), 40, seed=1)
    print(f"sweep: {exact} exact, {inexact} bounded, {checks} checks, {len(wrong)} wrong")
    assert wrong == [], wrong[:5]


OWN_PATTERNS = [
    (r"^(\.[A-Za-z_][A-Za-z0-9_]*|\[\d+\])*$", 0),
    (r"(\w+)\s+BETWEEN\s+(-?\d+(?:\.\d+)?)\s+AND\s+(-?\d+(?:\.\d+)?)", re.I),
    (r"(\w+)\s*(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)", 0),
    (r"decimal\(\s*(\d+)\s*,\s*(\d+)\s*\)", 0),
    (r"(?:var)?char\((\d+)\)", 0),
    (r"NOT NULL constraint failed: \w+\.(\w+)", 0),
    (r"CHECK constraint failed: ([^\n]+?)\s*(?:\n|$)", 0),
    (r"[a-z0-9]+(?:-[a-z0-9]+)*", 0),
]


def _corpus(n, seed=3175):
    rng = random.Random(seed)
    pieces = [".a", "[0]", "[12]", ".b_1", "x", " BETWEEN ", " between ", "1", "-2.5", " AND ",
              ">=", "<", " ", "decimal(", "10", ",", ")", "varchar(", "char(",
              "NOT NULL constraint failed: ", "t.c", "CHECK constraint failed: ", "\n", "a-b", "-",
              "٣", "é", "A", "\U00030000"]
    out = {""}
    while len(out) < n:
        out.add("".join(rng.choice(pieces) for _ in range(rng.randint(1, 5))))
    return sorted(out)


def test_the_package_own_validators_agree_with_re_on_a_corpus():
    corpus = _corpus(int(os.environ.get("MATHEMA_REGEX_CORPUS", "400")))
    total = sum(len(corpus) * len(PREDICATES) for _ in OWN_PATTERNS)
    wrong = [w for pattern, flags in OWN_PATTERNS for w in disagreements(pattern, flags, corpus)]
    assert wrong == [], (len(wrong), total, wrong[:5])


# -- review findings -----------------------------------------------------------

@pytest.mark.parametrize("pattern, flags", [
    (r"(?a:\w)\w", 0), (r"(?a:\d)", 0), (r"(?a:\s)x", 0), (r"(?a:(?i:k))", 0), (r"(?i:k)", 0),
    (r"(?a:\b)\w", 0), (r"(?a:(?u:\w))", 0), (r"(?u:(?a:\w))", 0), (r"(?ai:s)", 0),
    (r"(?u:\w)\w", re.A), (r"x(?u:\w)", re.A), (r"(?a)(?u:\d)", 0),
])
def test_a_scope_that_states_ascii_or_unicode_leaves_the_other(pattern, flags):
    texts = ["\u017fa", "a\u017f", "aa", "\u0663", "1", "\x1cx", " x", "\u212a", "k", "K", "\u00e9",
             "s", "S", "\u017f", "\u00e9a", "a", "x\u00e9"]
    assert disagreements(pattern, flags, texts) == []


def test_a_unicode_scope_in_an_ascii_pattern_is_a_bound():
    # re.search filters starts by the pattern's first set read under the pattern's own
    # flags, so it misses a match the scope alone would find
    assert re.fullmatch(r"(?u:\w)", "\u00e9", re.A) and not re.search(r"(?u:\w)", "\u00e9", re.A)
    doc = rx.term(r"(?u:\w)", re.A, "contains")
    assert not doc["exact"] and rx.member(doc, "\u00e9", "at_least")
    assert rx.term(r"(?a:\w)", 0, "contains")["exact"]


@pytest.mark.parametrize("pattern", [r"(a)(?i:\1)", r"(?i)((?-i:a))\1", r"(?i)(a)\1", r"(k)(?i:\1)x"])
def test_a_backreference_under_ignore_case_is_bounded_by_any_case(pattern):
    texts = ["aA", "aa", "AA", "Aa", "a", "k\u212ax", "kKx", "kkx", ""]
    for predicate in PREDICATES:
        assert not rx.term(pattern, 0, predicate, version=rx.RUNNING)["exact"]
    assert disagreements(pattern, 0, texts) == []


def test_membership_in_a_term_that_is_not_exact_names_a_bound():
    doc = rx.term(r"(a)\1")
    with pytest.raises(ValueError, match="not exact"):
        rx.member(doc, "aa")
    assert rx.member(doc, "aa", "at_least") and not rx.member(doc, "aa", "at_most")


@pytest.mark.parametrize("pattern", [r"(?:\b\w){32}", r"(?:^|a\b){0,32}", r"(?:\Ba|\bb|$){20}"])
def test_an_assertion_in_a_counted_repeat_is_written_out_in_bounded_time(pattern):
    import time
    started = time.monotonic()
    doc = rx.term(pattern, 0, "contains")
    assert time.monotonic() - started < 10
    assert len(json.dumps(doc)) < 2_000_000
    texts = ["", "a", "ab", "a b", "ba", "aaa", "a" * 32, "ab " * 10]
    if doc["exact"]:
        assert disagreements(pattern, 0, texts, ("contains",)) == []
