# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The translation of Python regular expressions to z3, held to `re`.

A pattern, its flags and a mode (`fullmatch`, `match`, `search`) are a
text language: the strings `re.<mode>(pattern, s, flags)` finds a match
in. The translation is that language as a z3 formula over a string,
`older` admitting at least what `re` admits and `newer` at most; where
it is exact the two are the same formula. Every check below asks z3
about one concrete string and compares the answer with `re` run on it:
equal where exact, bracketing where not.

Strings here use characters z3 holds (up to U+2FFFF); a string with a
higher character reads, to the translation, as the same string with
each such character replaced by U+2FFFF, and the bracketing tests check
that reading."""
import gc
import os
import random
import re
import sys

import pytest

z3 = pytest.importorskip("z3")

from mathema_language import smt  # noqa: E402

MODES = ("fullmatch", "match", "search")
H = smt._Z3_MAX_CHAR


_SOLVERS = {}


@pytest.fixture(autouse=True)
def _a_z3_context_of_its_own():
    """Each test leaves z3 as it found it: z3 keeps what its solvers learned
    for the life of their context, hundreds of megabytes over this file, so
    the solvers are dropped and the default context replaced when a test ends."""
    yield
    _SOLVERS.clear()
    z3.z3._main_ctx = None
    gc.collect()


def admitted(pattern, flags, mode, side, text):
    """Whether z3 finds `text` in the translation on `side`, asked of one
    solver per translation."""
    key = (pattern, flags, mode, side)
    if key not in _SOLVERS:
        x = z3.String("x")
        solver = z3.Solver()
        solver.add(smt._pattern(z3, pattern, flags, mode, x, side))
        _SOLVERS[key] = (solver, x)
    solver, x = _SOLVERS[key]
    solver.push()
    solver.add(x == smt._z3_text(z3, text))
    answer = solver.check()
    solver.pop()
    assert answer != z3.unknown, (pattern, text)
    return answer == z3.sat


def runs(pattern, flags, mode, text):
    return getattr(re, mode)(pattern, text, flags) is not None


def stand_in(text):
    """The string the translation reads `text` as."""
    return "".join(c if ord(c) <= H else chr(H) for c in text)


def agree(pattern, flags, texts, modes=MODES):
    """Every (mode, text) where the translation and `re` differ: empty when
    the translation is exact on these texts."""
    out = []
    for mode in modes:
        for text in texts:
            expected = runs(pattern, flags, mode, text)
            for side in ("older", "newer"):
                if admitted(pattern, flags, mode, side, text) != expected:
                    out.append((mode, side, text, expected))
    return out


# -- anchors ----------------------------------------------------------------

ANCHOR_TEXTS = ["", "a", "a\n", "a\n\n", "\na", "ab", "b\na", "a\nb", "\n", "aa"]


@pytest.mark.parametrize("pattern", [r"a$", r"a\Z", r"^a", r"\Aa", r"\Aa\Z", r"^a$", r"a$\n",
                                     r"$", r"\Z", r"^", r"a$$", r"(?:a$|b)", r"a(?:$|b)",
                                     r"$\n?", r"(^|b)a", r"a\Z\n?", r"\n$", r"^$"])
@pytest.mark.parametrize("flags", [0, re.M])
def test_anchors_read_as_re_reads_them(pattern, flags):
    assert agree(pattern, flags, ANCHOR_TEXTS) == []
    assert smt._exact(pattern, flags)


def test_dollar_admits_one_final_newline_and_end_of_string_admits_none():
    assert admitted(r"\Aa$", 0, "search", "newer", "a\n")
    assert not admitted(r"\Aa\Z", 0, "search", "older", "a\n")
    assert not admitted(r"\Aa$", 0, "search", "older", "a\n\n")


def test_a_json_schema_pattern_ending_in_end_of_string_is_proven_inside_its_one_member():
    # ml-smt-end-anchor-exact: a JSON Schema pattern is a search; \A(?:a)\Z
    # admits "a" alone, not "a\n"
    pytest.importorskip("jsonschema")
    older = {"type": "object", "properties": {"v": {"type": "string", "pattern": r"\A(?:a)\Z"}},
             "required": ["v"]}
    newer = {"type": "object", "properties": {"v": {"type": "string", "pattern": r"^a$"}},
             "required": ["v"]}
    result = smt._schema_inclusion(older, newer)
    assert result.verdict == "proven", result


# -- modes ------------------------------------------------------------------

def test_match_is_a_prefix_search_is_anywhere_fullmatch_is_the_whole():
    assert admitted("ab", 0, "match", "newer", "abc")
    assert not admitted("ab", 0, "match", "older", "cab")
    assert admitted("ab", 0, "search", "newer", "cab")
    assert not admitted("ab", 0, "fullmatch", "older", "abc")
    assert admitted("", 0, "search", "newer", "")


# -- flags ------------------------------------------------------------------

FLAG_TEXTS = ["a", "A", "\n", "k", "K", "K", "s", "S", "ſ", "İ", "i", "I",
              "ı", "ß", "ss", "ẞ", "σ", "ς", "Σ", "é", "É",
              "", "ab", "aB", "x\ny"]


@pytest.mark.parametrize("pattern, flags", [
    ("a", re.I), ("k", re.I), ("s", re.I), ("i", re.I), ("ß", re.I), ("σ", re.I),
    ("[a-z]", re.I), ("[^a-z]", re.I), ("[k-s]", re.I), (r"[à-ÿ]", re.I),
    ("k", re.I | re.A), ("[a-z]", re.I | re.A), ("(?i)k", 0), ("(?i:k)b", 0), ("(?i)a(?-i:b)", 0),
    (".", 0), (".", re.S), ("(?s:.)y", 0), ("x.y", 0), ("x.y", re.S), ("(?m)^y", 0),
    (" a  b # comment", re.X), ("(?x) a b", 0), ("[^\n]", re.I),
])
def test_flags_read_as_re_reads_them(pattern, flags):
    assert agree(pattern, flags, FLAG_TEXTS) == []


# -- quantifiers and structure ----------------------------------------------

@pytest.mark.parametrize("pattern", [r"a*?", r"a+?b", r"a{2,3}?", r"a??b", r"(?:ab|a)*c",
                                     r"(a|)b", r"a||b", r"((a)(b(c)?))+", r"a{0}", r"a{3}",
                                     r"(?:a{2}){2,}", r"[\x41-\x43]+", r"é\x0a",
                                     r"(?:a|b?)+c", r"(?:)*", r"(?:a*)*b"])
def test_repeats_groups_and_escapes_read_as_re_reads_them(pattern):
    texts = ["", "a", "aa", "aaa", "aaaa", "b", "ab", "aab", "abc", "c", "abab", "ababc",
             "aac", "A", "C", "AB", "é\n", "bc"]
    assert agree(pattern, 0, texts) == []
    assert smt._exact(pattern, 0)


def test_a_large_bound_is_kept_as_a_count():
    assert admitted(r"a{1000}", 0, "fullmatch", "newer", "a" * 1000)
    assert not admitted(r"a{1000}", 0, "fullmatch", "older", "a" * 999)
    assert admitted(r"[ab]{2,4000}", 0, "fullmatch", "newer", "ab" * 1000)


def test_a_unicode_class_in_a_repeat_is_decided_over_its_atoms():
    pattern = r"((.)??){1,3}([^\n]\W){0,2}"
    for text in [" ", "  ", "a ", "a b ", "\u00e9\u00e9", "\n"]:
        for mode in MODES:
            assert smt._decides(pattern, re.I, mode, "older", text) == runs(pattern, re.I, mode, text)


@pytest.mark.skipif(sys.version_info < (3, 11), reason="possessive repeats need Python 3.11")
def test_a_possessive_repeat_is_not_the_greedy_language():
    # a possessive repeat gives nothing back, so a*+a never matches
    assert re.fullmatch("a*a", "aa") and not re.fullmatch("a*+a", "aa")
    with pytest.raises(smt.Untranslated, match="possessive"):
        smt._pattern(z3, "a*+a", 0, "fullmatch", z3.String("x"), "older")


# -- untranslated -----------------------------------------------------------

@pytest.mark.parametrize("pattern, named", [
    (r"(a)\1", "backreference"), (r"(?=a)a", "lookahead"), (r"(?!a)b", "lookahead"),
    (r"(?<=a)b", "lookbehind"), (r"(?<!a)b", "lookbehind"), (r"(a)?(?(1)b|c)", "conditional"),
    (r"(?>a)", "atomic group"), (r"(?:\ba)*", "inside an unbounded repeat"),
    (r"[", "does not compile"),
])
def test_what_is_not_translated_is_named(pattern, named):
    if sys.version_info < (3, 11) and named == "atomic group":
        named = "does not compile"      # Python 3.10 does not read an atomic group
    with pytest.raises(smt.Untranslated, match=named):
        smt._pattern(z3, pattern, 0, "search", z3.String("x"), "older")
    with pytest.raises(smt.Untranslated, match=named):
        smt._exact(pattern, 0)


def test_a_bytes_pattern_and_the_locale_flag_are_not_translated():
    with pytest.raises(smt.Untranslated, match="bytes"):
        smt._exact(b"a", 0)
    with pytest.raises(smt.Untranslated):
        smt._exact("a", re.L)


# -- Unicode classes --------------------------------------------------------

def _chars(intervals):
    return {c for lo, hi in intervals for c in range(lo, hi + 1)}


@pytest.mark.parametrize("pattern, defined", [
    (r"\d", str.isdecimal),
    (r"\w", lambda c: c.isalnum() or c == "_"),
    (r"\s", str.isspace),
])
def test_unicode_classes_are_re_own_definitions(pattern, defined):
    expected = {cp for cp in range(0x110000) if defined(chr(cp))}
    assert _chars(smt._class_chars(pattern, 0)) == expected


def test_ascii_classes():
    assert _chars(smt._class_chars(r"\d", re.A)) == set(range(0x30, 0x3A))
    assert _chars(smt._class_chars(r"\s", re.A)) == {ord(c) for c in " \t\n\r\f\v"}


CLASS_TEXTS = ["0", "9", "٣", "๓", "²", "a", "Z", "_", "é", "一", " ",
               "\t", " ", " ", "\x1c", "　", "-", "\n", "Ⅷ", "½", ""]


@pytest.mark.parametrize("pattern", [r"\d", r"\w", r"\s", r"\D", r"\W", r"\S", r"[\d\s]",
                                     r"[^\w]", r"[^\W\d]", r"[\w-]", r"\b\w+\b", r"a\b", r"\B",
                                     r"\Ba", r"\b"])
@pytest.mark.parametrize("flags", [0, re.A])
def test_class_and_boundary_texts(pattern, flags):
    texts = CLASS_TEXTS + ["a b", "ab", " a", "a ", "éa", "0a"]
    assert agree(pattern, flags, texts) == []


def test_word_boundary_on_the_empty_string_reads_as_this_python_reads_it():
    for pattern in (r"\b", r"\B"):
        for mode in MODES:
            assert admitted(pattern, 0, mode, "older", "") == runs(pattern, 0, mode, "")


def test_a_class_past_z3_characters_is_bracketed_and_not_exact():
    # \w holds letters past U+2FFFF (CJK extension G) but not every character there
    assert not smt._exact(r"\w", 0)
    assert smt._exact(r"\d", 0)
    assert smt._exact(r".", 0)
    for text in ["\U00030000", "\U000E0001", "a\U00030000"]:
        for mode in MODES:
            expected = runs(r"\w+", 0, mode, text)
            older = admitted(r"\w+", 0, mode, "older", stand_in(text))
            newer = admitted(r"\w+", 0, mode, "newer", stand_in(text))
            assert (not expected or older) and (not newer or expected), (mode, text)


def test_a_literal_past_z3_characters_is_bracketed():
    assert not smt._exact("\U00030000", 0)
    assert admitted("\U00030000", 0, "fullmatch", "older", chr(H))
    assert not admitted("\U00030000", 0, "fullmatch", "newer", chr(H))


# -- the language object and the encoding -----------------------------------

def test_a_pattern_language_is_a_text_language_the_encoding_reads():
    lang = smt._PatternLanguage(r"[a-z]+$", re.I, "match")
    assert lang.contains("Abc\n") and not lang.contains("1abc") and not lang.contains(3)
    enc = smt.new_encoding(z3)
    x = z3.String("x")
    for text in ["Abc\n", "abc1", "", "abc\n\n"]:
        solver = z3.Solver()
        solver.add(enc.text(lang, x, "newer"), x == smt._z3_text(z3, text))
        assert (solver.check() == z3.sat) == lang.contains(text), text


def test_a_compiled_pattern_carries_its_flags():
    compiled = re.compile(r"ab$", re.I)
    assert admitted(compiled, 0, "search", "newer", "xAB\n")


def test_text_round_trips_through_z3():
    text = "a\\u{41}é\ud800\n" + chr(H)
    x = z3.String("x")
    solver = z3.Solver()
    solver.add(x == smt._z3_text(z3, text))
    assert solver.check() == z3.sat
    assert smt._text_of(solver.model(), x) == text


# -- differential -----------------------------------------------------------

ALPHABET = ["a", "b", "A", "\n", " ", "1", "٣", "_", "é", "K", "k", "-"]
ATOMS = ["a", "b", "k", ".", "[ab]", "[^a]", r"\d", r"\w", r"\s", r"\W", "[a-c]", r"\n", "-",
         "^", "$", r"\A", r"\Z", r"\b", r"\B", "", "[^\\n]"]


def _generate(rng, depth=0):
    roll = rng.random()
    if depth > 2 or roll < 0.35:
        return rng.choice(ATOMS)
    if roll < 0.6:
        return _generate(rng, depth + 1) + _generate(rng, depth + 1)
    if roll < 0.75:
        return "(?:" + _generate(rng, depth + 1) + "|" + _generate(rng, depth + 1) + ")"
    sub = _generate(rng, depth + 1)
    quant = rng.choice(["*", "+", "?", "{2}", "{1,3}", "{0,2}", "*?", "+?", "??"])
    return "(" + sub + ")" + quant


def _texts(rng, n):
    out = {"", "\n"}
    while len(out) < n:
        out.add("".join(rng.choice(ALPHABET) for _ in range(rng.randint(1, 5))))
    return sorted(out)


def _small(pattern, flags):
    """Whether the pattern's sets are few intervals, so z3 decides its
    formula over all of z3's characters quickly."""
    return sum(len(s) for s in smt._translated(pattern, flags).sets()) <= 64


def _sweep(n_patterns, n_texts, seed):
    """Each generated pattern, in each mode, on random texts: z3's answer
    over the pattern's atoms (`_decides`) against `re`, and, where the
    pattern's sets are small, the formula `_pattern` itself against both."""
    rng = random.Random(seed)
    translated = disagreements = checks = 0
    for _ in range(n_patterns):
        pattern = _generate(rng)
        flags = rng.choice([0, re.I, re.M, re.S, re.A, re.I | re.M, re.I | re.A])
        try:
            exact = smt._exact(pattern, flags)
        except smt.Untranslated:
            continue
        translated += 1
        small = _small(pattern, flags)
        for mode in MODES:
            for text in _texts(rng, n_texts):
                expected = runs(pattern, flags, mode, text)
                older = smt._decides(pattern, flags, mode, "older", text)
                newer = older if exact else smt._decides(pattern, flags, mode, "newer", text)
                checks += 1
                wrong = (expected and not older) or (newer and not expected) \
                    or (exact and older != expected)
                if small and not wrong:
                    checks += 1
                    wrong = admitted(pattern, flags, mode, "older", text) != older
                if wrong:
                    disagreements += 1
                    print("disagree", repr(pattern), flags, mode, repr(text), expected, older, newer)
    return translated, checks, disagreements


def test_generated_patterns_agree_with_re():
    translated, checks, disagreements = _sweep(60, 12, seed=20261119)
    assert translated >= 45 and disagreements == 0, (translated, checks, disagreements)


@pytest.mark.skipif(not os.environ.get("MATHEMA_REGEX_SWEEP"), reason="set MATHEMA_REGEX_SWEEP")
def test_a_large_sweep_agrees_with_re():
    n = int(os.environ["MATHEMA_REGEX_SWEEP"])
    translated, checks, disagreements = _sweep(n, 20, seed=1)
    print(f"sweep: {translated} patterns, {checks} checks, {disagreements} disagreements")
    assert disagreements == 0


# the package's own validators, against a fixed corpus of texts
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
              ">=", "<", " ", "decimal(", "10", ",", ")", "varchar(", "char(", "NOT NULL constraint failed: ",
              "t.c", "CHECK constraint failed: ", "\n", "a-b", "-", "٣", "é", "A"]
    out = {""}
    while len(out) < n:
        out.add("".join(rng.choice(pieces) for _ in range(rng.randint(1, 5))))
    return sorted(out)


def test_the_package_own_validators_agree_with_re_on_a_corpus():
    corpus = _corpus(int(os.environ.get("MATHEMA_REGEX_CORPUS", "60")))
    total = agreed = 0
    for pattern, flags in OWN_PATTERNS:
        for mode in MODES:
            for text in corpus:
                total += 1
                agreed += admitted(pattern, flags, mode, "older", text) == runs(pattern, flags, mode, text)
    assert agreed == total, (agreed, total)


# -- deciding between pattern languages ---------------------------------------

@pytest.mark.parametrize("a, b, verdict", [
    ((r"\Aa\Z", 0, "search"), (r"a", 0, "fullmatch"), "proven"),
    ((r"a$", 0, "search"), (r"a", 0, "search"), "proven"),
    ((r"^a$", 0, "search"), (r"a", 0, "fullmatch"), "falsified"),
    ((r"[a-z]+", 0, "fullmatch"), (r"[a-z]+", re.I, "fullmatch"), "proven"),
    ((r"[a-z]+", re.I, "fullmatch"), (r"[a-z]+", 0, "fullmatch"), "falsified"),
    ((r"\d+", re.A, "fullmatch"), (r"\d+", 0, "fullmatch"), "proven"),
    ((r"\d+", 0, "fullmatch"), (r"[0-9]+", 0, "fullmatch"), "falsified"),
    ((r"(a)\1", 0, "fullmatch"), (r"a+", 0, "fullmatch"), "unknown"),
])
def test_inclusion_between_pattern_languages(a, b, verdict):
    result = smt._text_inclusion(a, b)
    assert result.verdict == verdict, result
    if verdict == "falsified":
        w = result.witness
        assert runs(*a[:2], a[2], w) and not runs(*b[:2], b[2], w)
    if verdict == "unknown":
        assert "backreference" in result.reason


def test_emptiness_disjointness_and_equivalence():
    assert smt._text_emptiness((r"a\Zb", 0, "search")).verdict == "proven"
    nonempty = smt._text_emptiness((r"a$\n", 0, "search"))
    assert nonempty.verdict == "falsified" and re.search(r"a$\n", nonempty.witness)
    assert smt._text_disjointness((r"\d+", 0, "fullmatch"), (r"[a-z]+", 0, "fullmatch")).verdict == "proven"
    common = smt._text_disjointness((r"\w+", 0, "fullmatch"), (r"\d", 0, "fullmatch"))
    assert common.verdict == "falsified" and re.fullmatch(r"\d", common.witness)
    assert smt._text_equivalence((r"a$", 0, "fullmatch"), (r"a", 0, "fullmatch")).verdict == "proven"
    assert smt._text_equivalence((r"a+?", 0, "match"), (r"a", 0, "match")).verdict == "proven"
    differ = smt._text_equivalence((r"a$", 0, "match"), (r"a\Z", 0, "match"))
    assert differ.verdict == "falsified"
    assert runs(r"a$", 0, "match", differ.witness) != runs(r"a\Z", 0, "match", differ.witness)
