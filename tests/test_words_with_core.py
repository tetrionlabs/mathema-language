# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The words this package registers, read, rendered, resolved and
decided by mathema itself. Skipped on a mathema without the word
registry. A claim written with a pattern word resolves, and its relation
to an alphabet language is decided from the two terms; every example and
every did-you-mean the words print parses and renders back to itself;
each word read where it has no meaning is refused with the language that
was meant; a call in code is read as the word it states."""
import functools
import random
import re

import pytest

languages = pytest.importorskip("mathema.languages")
if not hasattr(languages, "PredicateWord"):
    pytest.skip("this mathema has no word registry", allow_module_level=True)

from mathema.conjecture import check_conjectures, claim  # noqa: E402
from mathema.domain import InvalidDomain, parse_binding  # noqa: E402

from mathema_language import words  # noqa: E402
from mathema_language.text import _regular  # noqa: E402
from mathema_language.text.pattern import Pattern  # noqa: E402

HERE = __name__
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
POSTCODE = Pattern("AA99[ ]9AA", "ascii")


def _ref(text):
    return parse_binding(f"s in {text}")[1].pieces[0]


def _canonical(text):
    return "L[" + _ref(text).text + "]"


def _resolve(text):
    return languages.resolve_language(_ref(text))


def _same(s: str) -> str:
    return s


def _relation(text):
    (result,) = check_conjectures(_same, [claim(text)])
    return result


def test_the_words_and_the_alphabet_constructor_are_registered_through_the_entry_points():
    assert {w.word for w in languages.predicate_words()} >= {
        "matches", "contains", "starts with", "ends with", "within", "pattern"}
    assert languages.predicate_word("startsWith") is words.STARTS_WITH
    assert languages.alphabet_constructor() is words.ALPHABET
    assert languages.word_for_sugar("^=") is words.STARTS_WITH
    assert languages.word_for_sugar("in") is None
    assert languages.resolve_language("lower").contains("abc")
    assert not languages.resolve_language("upper").contains("abc")


def test_a_pattern_claim_is_a_subset_of_its_alphabet_and_the_reverse_fails_at_the_empty_string():
    pytest.importorskip("z3")
    pattern = 'L[unicode, matches (re(r"[a-z0-9-]+\\Z", python))]'
    alphabet = 'L[lower + digit + "-"]'
    proven = _relation(f"{pattern} subset {alphabet}")
    assert proven.verdict == "proven", proven.note
    assert proven.statement == f"{pattern} subset {alphabet}"
    refuted = _relation(f"{alphabet} subset {pattern}")
    assert refuted.verdict == "falsified", refuted.note
    assert str(refuted.counterexample).startswith("'' is in L[lower + digit + \"-\"] and not in ")


@pytest.mark.parametrize("smaller, larger, witness", [
    ('L[ascii, pattern ("AA99[ ]9AA")]', 'L[alnum + " "]', None),
    ('L[alnum + " "]', 'L[ascii, pattern ("AA99[ ]9AA")]', ""),
    ('L[path, within ("/workspace/src")]', 'L[path, within "/workspace"]', None),
    ('L[unicode, starts with ("http://")]', 'L[unicode, contains ("://")]', None),
    ('L[unicode, contains ("://")]', 'L[unicode, starts with ("http://")]', "://"),
    ('L[ascii, ^= "ab"]', 'L[ascii, contains (re("B", ignoreCase))]', None),
    ('L[ascii, pattern ("AW{0+}", W = alnum + "_")]', 'L[unicode, matches (re(r"[A-Za-z]\\w*\\Z", python))]', None),
    ('L[unicode, starts with (re(r"[a-z]+$", python))]', 'L[lower]', "a\n"),
    ('L[unicode, matches (re(r"[a-z]+$", python))]', 'L[lower]', None),
    ('L[unicode, matches (re(r"[a-z]+$", python))]', 'L[unicode, starts with (re(r"[a-z]+$", python))]', None),
    (f"L[unicode, matches ({HERE}.SLUG)]", 'L[lower + digit + "-"]', None),
    (f"L[unicode, matches ({HERE}.POSTCODE)]", 'L[ascii, pattern ("AA99[ ]9AA")]', None),
    ('L[ascii, pattern ("AA99")]', 'L[ascii, pattern ("AA99", A = upper)]', "aa00"),
    ('L[lower, len <= 3]', 'L[lower + digit, not contains (re(r"[0-9]", python))]', None),
], ids=lambda value: value if isinstance(value, str) and value.startswith("L[") else None)
def test_relations_between_the_registered_languages_are_decided_from_their_terms(smaller, larger, witness):
    pytest.importorskip("z3")
    result = _relation(f"{smaller} subset {larger}")
    if witness is None:
        assert result.verdict == "proven", (result.verdict, result.note, result.counterexample)
    else:
        assert result.verdict == "falsified", (result.verdict, result.note)
        found = str(result.counterexample)
        assert " is in L[" in found and " and not in L[" in found
        assert _resolve(smaller).contains(witness) and not _resolve(larger).contains(witness)


CANONICAL = [
    ('L[unicode, matches(re("[a-z]+"))]', 'L[unicode, matches (re(r"[a-z]+", python))]'),
    ('L[unicode, Matches (re(r"(?i)[a-z]+", multiline, PYTHON, dotAll))]',
     'L[unicode, matches (re(r"[a-z]+", python, dot all, ignore case, multi line))]'),
    ('L[ascii, ^= "ab"]', 'L[ascii, starts with ("ab")]'),
    ('L[ascii, $= ".csv"]', 'L[ascii, ends with (".csv")]'),
    ('L[ascii, starts_with("a"), endsWith ("b")]', 'L[ascii, ends with ("b"), starts with ("a")]'),
    ('L[path, within "/ws"]', 'L[path, within ("/ws")]'),
    ('L[path, WITHIN("/a",  "/b")]', 'L[path, within ("/a", "/b")]'),
    ('L[iso_date, within ("2026-01-01", "2026-12-31")]', 'L[iso_date, within ("2026-01-01", "2026-12-31")]'),
    ('L[ascii, pattern ("AW{0+}", W = "_" + alnum)]', 'L[ascii, pattern ("AW{0+}", W = alnum + "_")]'),
    ('L[ascii, pattern("ZA9", Z = upper, A = lower, 9 = hexdigit)]', 'L[ascii, pattern ("ZA9", 9 = hexdigit, A = lower, Z = upper)]'),
    ('L[unicode, matches (pattern ("AA99", A = upper))]', 'L[unicode, matches (pattern("AA99", A = upper))]'),
    ('L["_" + digit + lower, len <= 8]', 'L[lower + digit + "_", len <= 8]'),
    ('L[lower + "ba" + "a"]', 'L[lower + "a" + "b"]'),
]


@pytest.mark.parametrize("written, canonical", CANONICAL, ids=[c[0] for c in CANONICAL])
def test_every_spelling_renders_to_the_canonical_text_and_that_text_to_itself(written, canonical):
    assert _canonical(written) == canonical
    assert _canonical(canonical) == canonical


def test_every_example_the_words_carry_parses_renders_back_to_itself_and_resolves():
    examples = [text for word in words._WORDS.values() for text in word.examples.values()]
    assert len(examples) >= 11
    for text in examples:
        assert _canonical(text) == text, text
        language = _resolve(text)
        assert languages.language_problems(language) == [], text
        assert "L[" + language.name + "]" == text


RESOLVED = ['L[unicode, matches (re(r"[a-z0-9-]+\\Z", python))]', 'L[ascii, starts with ("ab"), len <= 6]',
            'L[ascii, not contains (re(r"[0-9]", python)), len in [1, 8]]', 'L[unicode, ends with (".csv")]',
            'L[ascii, pattern ("AW{0+}", W = alnum + "_")]', 'L[ascii, not pattern ("AA")]',
            'L[path, len <= 20, within ("/ws")]', 'L[ipv4, within ("10.0.0.0/8", "192.168.0.0/16")]',
            'L[iso_date, not within ("2026-01-01", "2026-12-31")]', 'L[lower + digit + "_", len in [3, 32]]',
            f"L[unicode, matches ({HERE}.SLUG)]", 'L[ascii, matches (pattern("AA99[ ]9AA"))]',
            'L[unicode, contains (pattern("99"))]']


@pytest.mark.parametrize("text", RESOLVED)
def test_a_registered_language_resolves_passes_the_language_checks_and_draws_members(text):
    language = _resolve(text)
    assert languages.language_problems(language) == []
    rng = random.Random(52)
    assert all(language.contains(language.sample(rng)) for _ in range(40))
    for seed in range(20):
        outside = language.outside(random.Random(seed))
        assert outside is None or not language.contains(outside)


def test_a_pattern_language_over_unicode_states_the_pattern_s_own_term():
    language = _resolve('L[unicode, matches (re(r"[a-z0-9-]+\\Z", python))]')
    doc = language.to_json()["term"]
    assert doc["exact"] is True
    assert _regular.term_hash(doc) == _regular.term_hash(_regular.term(r"[a-z0-9-]+\Z", 0, "matches"))
    over_ascii = _resolve('L[ascii, matches (re(r"\\w+", python))]').to_json()["term"]
    assert _regular.member(over_ascii, "a_1") and not _regular.member(over_ascii, "é")


REFUSED = [
    ('L[ascii, *= "a"]', "no registered predicate reads `*=`", None),
    ('L[ascii, == "a"]', "no registered predicate reads `==`", None),
    ('L[ascii, != "a"]', "no registered predicate reads `!=`", None),
    ('L[ascii, in re(r"a+")]', "no registered predicate reads `in`", None),
    ('L[unicode, matches ("a", "b")]', "matches takes one argument, a pattern", None),
    ('L[unicode, matches (re(r"[a-z]+", javascript))]', "the javascript dialect is not available yet.",
     're(r"[a-z]+", python)'),
    ('L[unicode, contains (re(r"a", js, ignore case))]', "is neither a dialect nor a flag of re", None),
    ('L[unicode, starts with (re(r"a", ecma))]', "is neither a dialect nor a flag of re", None),
    *[(f'L[unicode, matches (re(r"a+", {word}))]', f"the {named} dialect is reserved, not available yet.",
       're(r"a+", python)') for word, named in sorted(words._RESERVED.items())],
    ('L[unicode, matches (re(r"a", ignorcase))]', "Did you mean ignore case?", None),
    ('L[unicode, matches (re(r"a", python 3.9))]', "python 3.9 is not a supported version", None),
    ('L[unicode, matches (re(r"("))]', 'the pattern r"(" does not compile', None),
    ('L[ascii, pattern ("KEY-99")]', "K, E and Y are not symbols. For the literal text write 'KEY': "
                                   "pattern (\"'KEY'-99\").", None),
    ('L[path, within (ws)]', 'within takes quoted arguments, within ("/workspace"), not \'ws\'', None),
]


@pytest.mark.parametrize("written, said, meant", REFUSED, ids=[r[0] for r in REFUSED])
def test_an_argument_a_word_refuses_is_refused_when_the_claim_is_read_and_what_it_offers_parses(
        written, said, meant):
    with pytest.raises(InvalidDomain) as caught:
        _ref(written)
    message = str(caught.value)
    assert said in message
    if meant is not None:
        assert message.endswith(f"Did you mean {meant}?")
        word = _ref(written.replace("javascript", "python")).predicates[0].word if "javascript" in written \
            else "matches" if "matches" in written else "contains" if "contains" in written else "starts with"
        offered = f"L[unicode, {word} ({meant})]"
        assert _canonical(offered) == offered
        assert languages.language_problems(_resolve(offered)) == []


MEANINGLESS = [
    ('L[json, within ("/ws")]',
     "L[json, within (\"/ws\")]: 'within' has no meaning for L[json]: it applies to a path, an IPv4 address, "
     "an IPv6 address, a date or a datetime, for example L[path, within (\"/workspace\")]. "
     "Did you mean L[path, within (\"/ws\")]?", 'L[path, within ("/ws")]'),
    ('L[unicode, within ("10.0.0.0/8")]', None, 'L[ipv4, within ("10.0.0.0/8")]'),
    ('L[unicode, within ("2026-01-01", "2026-12-31")]', None, 'L[iso_date, within ("2026-01-01", "2026-12-31")]'),
    ('L[iso_date, pattern ("9999-99-99")]',
     "L[iso_date, pattern (\"9999-99-99\")]: 'pattern' has no meaning for L[iso_date]: it applies to text in "
     "L[ascii] or text in L[unicode], for example L[ascii, pattern (\"AA99[ ]9AA\")]. "
     "Did you mean L[ascii, pattern (\"9999-99-99\")]?", 'L[ascii, pattern ("9999-99-99")]'),
    ('L[json, pattern ("AW", W = upper)]', None, 'L[ascii, pattern ("AW", W = upper)]'),
]


@pytest.mark.parametrize("written, message, meant", MEANINGLESS, ids=[m[0] for m in MEANINGLESS])
def test_a_word_with_no_meaning_over_the_base_is_refused_with_the_language_that_was_meant(written, message, meant):
    with pytest.raises(languages.MeaninglessPredicate) as caught:
        _resolve(written)
    if message is not None:
        assert str(caught.value) == message
    assert caught.value.suggestion == meant
    assert str(caught.value).endswith(f"Did you mean {meant}?")
    for text in (caught.value.suggestion, caught.value.example):
        assert _canonical(text) == text
        assert languages.language_problems(_resolve(text)) == []


def test_the_word_shape_is_refused_when_the_language_is_resolved_and_pattern_is_named():
    with pytest.raises(InvalidDomain) as caught:
        _resolve('L[ascii, shape ("AA99")]')
    assert "shape" in str(caught.value) and "pattern" in str(caught.value)


def test_an_argument_of_the_wrong_form_for_the_base_is_refused_with_the_form_and_the_language_meant():
    with pytest.raises(ValueError) as caught:
        _resolve('L[ipv4, within ("/root")]')
    assert str(caught.value) == ('L[ipv4, within ("/root")]: within ("/root") is not an address block for L[ipv4]: it expects a CIDR '
                                 'block such as "10.0.0.0/8". Did you mean L[path, within ("/root")]?')
    assert _canonical('L[path, within ("/root")]') == 'L[path, within ("/root")]'
    with pytest.raises(ValueError) as caught:
        _resolve('L[iso_date, within ("2026-01-01")]')
    assert "takes 2 arguments, an interval of dates, not 1" in str(caught.value)
    assert str(caught.value).endswith('Did you mean L[iso_date, within ("2026-01-01", "2026-12-31")]?')
    with pytest.raises(InvalidDomain) as caught:
        _resolve('L[ascii, pattern ("A-\u00e9")]')
    assert "\u00e9 is not a symbol" in str(caught.value)
    with pytest.raises(ValueError) as caught:
        _resolve("L[ascii, pattern (\"A-'\u00e9'\")]")
    assert "expected an ASCII character in a pattern over ascii at position 3" in str(caught.value)


def test_a_pattern_word_on_a_language_that_is_not_text_is_refused():
    from dataclasses import dataclass

    @dataclass
    class Row:
        name: str

    from mathema_language.schema.adaptors.dataclass import adapt
    languages.register_language("rows_for_words", adapt(Row))
    try:
        with pytest.raises(languages.MeaninglessPredicate) as caught:
            _resolve('L[rows_for_words, starts with ("ab")]')
        assert "'starts with' has no meaning for L[rows_for_words]: it applies to text, for example " \
               'L[unicode, starts with (re(r"[a-z]+", python))]. Did you mean L[unicode, starts with ("ab")]?' \
               in str(caught.value)
        assert _canonical(caught.value.suggestion) == caught.value.suggestion
    finally:
        languages.unregister_language("rows_for_words")


def test_an_unknown_word_near_a_registered_one_and_an_unknown_alphabet_are_offered():
    with pytest.raises(languages.UnknownPredicate) as caught:
        _resolve('L[unicode, matchs ("a")]')
    assert str(caught.value).endswith('Did you mean L[unicode, matches ("a")]?')
    with pytest.raises(languages.UnknownLanguage) as caught:
        _resolve("L[lowr + digit]")
    assert "'lowr' is not a named alphabet" in str(caught.value) and "Did you mean lower?" in str(caught.value)


def test_a_call_in_code_is_read_as_the_word_it_states():
    insensitive = re.compile(r"[a-z]+", re.IGNORECASE | re.MULTILINE)
    assert words.MATCHES.reads_call(SLUG.fullmatch) == ('re(r"[a-z0-9]+(?:-[a-z0-9]+)*", python)',)
    assert words.CONTAINS.reads_call(insensitive.search) == ('re(r"[a-z]+", python, ignore case, multi line)',)
    assert words.STARTS_WITH.reads_call(SLUG.match) == ('re(r"[a-z0-9]+(?:-[a-z0-9]+)*", python)',)
    assert words.MATCHES.reads_call(SLUG.search) is None and words.CONTAINS.reads_call(SLUG.fullmatch) is None
    assert words.ENDS_WITH.reads_call(SLUG.fullmatch) is None
    assert words.MATCHES.reads_call(functools.partial(re.fullmatch, r"\d+")) == ('re(r"\\d+", python)',)
    assert words.CONTAINS.reads_call(functools.partial(re.search, "a", flags=re.I)) == (
        're(r"a", python, ignore case)',)
    assert words.MATCHES.reads_call(re.fullmatch) is None and words.MATCHES.reads_call(len) is None
    assert words.MATCHES.reads_call(re.compile(rb"a").fullmatch) is None
    word, arguments = languages.word_reading_call(SLUG.fullmatch)
    assert word is words.MATCHES
    text = f"L[unicode, {word.word} ({', '.join(arguments)})]"
    assert _canonical(text) == text
    language = _resolve(text)
    for candidate in ["a-b", "a--b", "", "a\n", "A"]:
        assert language.contains(candidate) == (SLUG.fullmatch(candidate) is not None)
    assert languages.word_reading_call(len) is None
