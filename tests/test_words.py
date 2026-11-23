# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The argument texts the registered words read and write, without
mathema's registry: `re(...)` with its dialect and flags in canonical
order, the dialects that are not available, the four kinds of pattern
argument, the pieces of an alphabet expression in canonical order, and
the meeting of two terms under a predicate and under its negation."""
import random
import re

import pytest

from mathema_language import words
from mathema_language.text import ASCII, UNICODE, _regular
from mathema_language.text.pattern import Pattern

POSTCODE = Pattern("AA99[ ]9AA", "ascii")
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*", re.IGNORECASE)


@pytest.mark.parametrize("written, canonical", [
    ('re("[a-z]+")', 're(r"[a-z]+", python)'), ("re(r'[a-z]+', python)", 're(r"[a-z]+", python)'),
    ('re(r"a", multiline, ignoreCase)', 're(r"a", python, ignore case, multi line)'),
    ('re(r"a", Dot_All, python, ASCII ONLY, verbose)', 're(r"a", python, ascii only, dot all, verbose)'),
    ('re(r"(?i)a")', 're(r"a", python, ignore case)'), ('re(r"(?ms)a(?i:b)", ignore case)',
                                                       're(r"a(?i:b)", python, dot all, ignore case, multi line)'),
    ('re("a\\"b")', 're("a\\"b", python)'), ('re(r"a\\\\")', 're("a\\\\\\\\", python)'),
    ('re("a\\nb")', 're("a\\nb", python)'), ('RE (r"\\d+\\Z")', 're(r"\\d+\\Z", python)'),
    ('re(r"a,b(c)", python)', 're(r"a,b(c)", python)'),
])
def test_re_is_written_with_its_dialect_and_its_flags_sorted(written, canonical):
    pattern, flags = words._read_re(written)
    assert words._re_text(pattern, flags) == canonical
    assert words._read_re(canonical) == (pattern, flags)
    assert words._canonical_pattern_argument(written) == canonical


@pytest.mark.parametrize("word", ["javascript", "JavaScript"])
def test_the_javascript_dialect_is_refused_as_not_available_with_the_python_call(word):
    with pytest.raises(ValueError) as caught:
        words._read_re(f're(r"[a-z]+", {word}, ignore case)')
    assert str(caught.value) == ('the javascript dialect is not available yet. '
                                 'Did you mean re(r"[a-z]+", python, ignore case)?')
    assert words._read_re('re(r"[a-z]+", python, ignore case)') == ("[a-z]+", int(re.IGNORECASE))


@pytest.mark.parametrize("word, named", sorted(words._RESERVED.items()))
def test_every_other_dialect_word_is_reserved(word, named):
    with pytest.raises(ValueError) as caught:
        words._read_re(f're(r"a+", {word})')
    assert str(caught.value) == (f'the {named} dialect is reserved, not available yet. '
                                 'Did you mean re(r"a+", python)?')


@pytest.mark.parametrize("written, said", [
    ('re(r"a", ignorcase)', "is neither a dialect nor a flag of re; the flags are ascii only, dot all, "
                            "ignore case, multi line, verbose. Did you mean ignore case?"),
    ('re(r"a", pyhton)', "Did you mean python?"),
    ('re(r"a", python 3.9)', "python 3.9 is not a supported version"),
    ('re(r"a", 3.13)', "a version is written python 3.13"),
    ('re(r"a", python, py)', "is neither a dialect nor a flag of re"),
    ('re(r"a", js)', "is neither a dialect nor a flag of re"),
    ('re(r"a", ecma)', "is neither a dialect nor a flag of re"),
    ('re(r"(")', 'the pattern r"(" does not compile'),
    ("re(a)", "re takes a quoted pattern first"), ("re()", "re takes a quoted pattern first"),
])
def test_a_call_of_re_that_does_not_read_says_why(written, said):
    with pytest.raises(ValueError) as caught:
        words._read_re(written)
    assert said in str(caught.value)


def test_what_is_not_a_call_of_re_is_not_read_as_one():
    assert words._read_re('"re(a)"') is None and words._read_re("shape(\"AA\")") is None
    assert words._read_re("app.re") is None


def test_a_flag_with_no_word_is_refused():
    assert words._re_text("a", re.UNICODE) == 're(r"a", python)'
    with pytest.raises(ValueError):
        words._re_text("a", re.DEBUG)


@pytest.mark.parametrize("written, sugar, canonical", [
    ('"http://"', None, '"http://"'), ("'a\"b'", None, '"a\\"b"'), ('"a"', None, '"a"'), ('"a"', "^=", '"a"'),
    ('re("a+")', None, 're(r"a+", python)'), ("app.text.SLUG", None, "app.text.SLUG"),
    ('pattern ( "AW{0+}", W = "_" + alnum )', None, 'pattern("AW{0+}", W = alnum + "_")'),
    ('pattern("\\\\K\\\\E\\\\Y-99")', None, 'pattern("\'KEY\'-99")'), (' app.PAT ', None, "app.PAT"),
])
def test_a_pattern_argument_is_a_literal_a_call_of_re_a_pattern_or_a_dotted_name(written, sugar, canonical):
    assert words._canonical_pattern_argument(written, sugar) == canonical
    assert words._canonical_pattern_argument(canonical, sugar) == canonical


@pytest.mark.parametrize("written, sugar, said", [
    ("PAT", None, "is not a pattern: write a quoted literal"), ("3", None, "is not a pattern"),
    ('pattern("KEY-99")', None, "K, E and Y are not symbols."), ("pattern(AA)", None, "pattern takes a quoted picture first"),
    ('pattern("AW", W == upper)', None, "a binding is SYMBOL = alphabet"),
    ('pattern("AW", W = upper, W = lower)', None, "the symbol W is bound twice"),
])
def test_an_argument_that_is_no_pattern_or_not_the_kind_an_operator_takes_is_refused(written, sugar, said):
    with pytest.raises(ValueError) as caught:
        words._canonical_pattern_argument(written, sugar)
    assert said in str(caught.value)


@pytest.mark.parametrize("argument, base, text, held", [
    ('"a.b"', "unicode", "a.b", True), ('"a.b"', "unicode", "axb", False),
    ('re(r"[a-z]+", python, ignore case)', "unicode", "aB", True),
    ('pattern("AA99")', "ascii", "ab12", True), ('pattern("AA99")', "ascii", "éb12", False),
    ('pattern("AA99")', "unicode", "éb12", True), ('pattern("AA99")', "json", "éb12", True),
    ("tests.test_words.SLUG", "unicode", "A-b", True), ("tests.test_words.POSTCODE", "unicode", "SW19 3AB", True),
])
def test_each_kind_of_argument_reads_as_one_python_pattern(argument, base, text, held):
    assert words._regex_language_of(argument, "matches", base).contains(text) == held


@pytest.mark.parametrize("name, said", [
    ("tests.test_words.MISSING", "nothing is named tests.test_words.MISSING"),
    ("tests.test_words.random", "names module, not a compiled pattern or a Pattern"),
    ("no_such_package.PAT", "nothing is named no_such_package.PAT"),
])
def test_a_dotted_name_of_anything_else_is_refused_when_it_is_resolved(name, said):
    with pytest.raises(ValueError) as caught:
        words._regex_of(name, "unicode")
    assert said in str(caught.value)
    assert words._canonical_pattern_argument(name) == name


def test_alphabet_pieces_are_ordered_names_first_then_characters_by_code_point():
    pieces = (("char", "_"), ("name", "digit"), ("char", "-"), ("name", "lower"), ("char", "_"),
              ("name", "lowr"))
    assert words._order_alphabet(pieces) == (("name", "lower"), ("name", "digit"), ("name", "lowr"),
                                            ("char", "-"), ("char", "_"))
    language = words._build_alphabet(pieces[:5])
    assert language.name == 'lower + digit + "-" + "_"'
    assert language.contains("a-1_") and not language.contains("A")
    with pytest.raises(ValueError) as caught:
        words._build_alphabet(pieces)
    assert "'lowr' is not a named alphabet" in str(caught.value) and "Did you mean lower?" in str(caught.value)


@pytest.mark.parametrize("negated", [False, True])
def test_a_base_under_a_predicate_is_the_two_languages_met_and_states_the_met_term(negated):
    inner = _regular.regex_language(r"[a-z]+\d?", "matches")
    language = words._narrowed(ASCII, inner, 'matches (re(r"[a-z]+\\d?", python))', negated)
    doc = language.to_json()["term"]
    assert doc["exact"] is True
    rng = random.Random(51)
    texts = [language.sample(rng) for _ in range(60)] + [ASCII.sample(rng) for _ in range(200)]
    texts += [inner.sample(rng) for _ in range(60)] + ["", "abc", "abc1", "ab٣", "é", "a1b"]
    texts += [t for t in (language.outside(random.Random(s)) for s in range(40)) if t is not None]
    assert any(language.contains(t) for t in texts) and not all(language.contains(t) for t in texts)
    for text in texts:
        expected = ASCII.contains(text) and (inner.contains(text) != negated)
        assert language.contains(text) == expected == _regular.member(doc, text), text


def test_meeting_with_a_bound_gives_a_bound_on_the_right_side_under_negation():
    inner = _regular.regex_language(r"(a|b)\1", "matches")
    assert inner.to_json()["term"]["exact"] is False
    for negated in (False, True):
        language = words._narrowed(UNICODE, inner, "x", negated)
        doc = language.to_json()["term"]
        assert doc["exact"] is False and doc["source"]["not_exact"] == ["a backreference"]
        for text in ["aa", "bb", "ab", "ba", "", "a", "aab"]:
            if language.contains(text):
                assert _regular.member(doc, text, "at_least"), text
            if _regular.member(doc, text, "at_most"):
                assert language.contains(text), text
