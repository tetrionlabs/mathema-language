# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""An alphabet expression is named alphabets and single characters
joined by `+`; its canonical text names the alphabets in a fixed order,
then the characters by code point, one to a pair of quotes. The language
of every string over it has an exact term, draws written from the
alphabet, and near misses with one character from outside it. A custom
alphabet defined in code is named in a claim by its dotted path and
states its term."""
import json
import random
import re

import mathema.languages as languages
import pytest

from mathema_language.text import _regular
from mathema_language.text.alphabet import (
    LOWER,
    NAMES,
    UPPER,
    USERNAME_CHARACTERS,
    Alphabet,
    AlphabetError,
    alphabet,
    alphabet_language,
    alphabet_refusal,
    named_ranges,
    parse_alphabet,
)


@pytest.mark.parametrize("written, canonical", [
    ('lower + digit + "_"', 'lower + digit + "_"'), ('"_" + digit + lower', 'lower + digit + "_"'),
    ('alnum+"_-"', 'alnum + "-" + "_"'), ("hex", "hex"), ("upper + upper", "upper"),
    ("'b' + 'a' + \"a\"", '"a" + "b"'), ('digit + "\\""', 'digit + "\\""'), ('"\\\\"', '"\\\\"'),
    (' lower  +  " " ', 'lower + " "'), ("unicode_alpha + digit + alpha", "unicode_alpha + alpha + digit"),
    ("latin-1 + 'é'", 'latin-1 + "é"'),
])
def test_the_canonical_text_names_alphabets_in_a_fixed_order_then_characters_by_code_point(written, canonical):
    found = parse_alphabet(written)
    assert found.text == canonical
    assert parse_alphabet(canonical) == found and parse_alphabet(canonical).text == canonical


@pytest.mark.running_unicode
def test_named_alphabets_are_the_registered_alphabet_languages_and_three_more():
    assert named_ranges("upper") == ((65, 90),) and named_ranges("lower") == ((97, 122),)
    assert named_ranges("hex") == ((48, 57), (65, 70), (97, 102))
    assert named_ranges("alnum") == ((48, 57), (65, 90), (97, 122))
    assert named_ranges("unicode") == ((0, 0x10FFFF),)
    for name in NAMES:
        if name in ("upper", "lower", "hex"):
            continue
        language = languages.resolve_language(name)
        ranges = named_ranges(name)
        rng = random.Random(41)
        for code in [0, 65, 97, 48, 95, 0xE9, 0x663, 0x4E2D, 0x1F600, *[rng.randrange(0x110000) for _ in range(300)]]:
            inside = any(lo <= code <= hi for lo, hi in ranges)
            assert language.contains(chr(code)) == inside == alphabet(name).has(chr(code)), (name, code)


@pytest.mark.parametrize("written, position, expected, found", [
    ("", 0, "the name of an alphabet or a quoted character", "the end of the expression"),
    ("lower +", 7, "the name of an alphabet or a quoted character", "the end of the expression"),
    ("lower digit", 6, '"+" between the parts', '"d"'),
    ("lowr + digit", 0, "a named alphabet (" + ", ".join(NAMES) + ")", '"lowr"; did you mean lower?'),
    ('lower + ""', 9, "a character between the quotes", "nothing"),
    ('lower + "a', 8, "the name of an alphabet or a quoted character", '""a"'),
    ("lower + 9", 8, "the name of an alphabet or a quoted character", '"9"'),
])
def test_an_expression_that_does_not_read_says_what_was_expected_and_where(written, position, expected, found):
    with pytest.raises(AlphabetError) as caught:
        parse_alphabet(written)
    assert (caught.value.position, caught.value.expected, caught.value.found) == (position, expected, found)
    assert alphabet_refusal(written) == str(caught.value)
    assert alphabet_refusal('lower + "_"') is None


def test_alphabets_add_and_a_string_adds_each_of_its_characters():
    assert (alphabet("lower") + "_-").text == 'lower + "-" + "_"'
    assert ("_" + alphabet("lower") + alphabet("digit")).text == 'lower + digit + "_"'
    assert alphabet("lower") + "_" == parse_alphabet('"_" + lower')
    assert hash(alphabet("lower") + "_") == hash(parse_alphabet('"_" + lower'))
    with pytest.raises(ValueError):
        Alphabet((), ())
    with pytest.raises(ValueError):
        Alphabet(("letters",), ())
    with pytest.raises(TypeError):
        alphabet("lower") + 3


@pytest.mark.running_unicode
@pytest.mark.parametrize("expression", ['lower + digit + "_"', "hex", "upper", 'alnum + "-" + "." + "_"',
                                        "unicode_alpha + digit", '"a" + "b"', "unicode", "ascii"])
def test_the_language_over_an_alphabet_draws_directly_and_states_an_exact_term(expression):
    language = alphabet_language(expression)
    found = alphabet(expression)
    assert language.name == found.text
    assert languages.language_problems(language) == []
    doc = language.to_json()["definition"]
    assert doc["exact"] is True and json.loads(json.dumps(doc)) == doc
    assert doc["source"]["alphabet"] == found.text
    assert language.to_json()["alphabet"] == {"names": list(found.names), "characters": list(found.characters)}
    rng = random.Random(42)
    drawn = [language.sample(rng) for _ in range(300)]
    assert "" in drawn and len(set(drawn)) > 30
    for text in drawn + [h.value for h in language.hazards() if len(h.value) < 100]:
        assert all(found.has(c) for c in text) and language.contains(text)
        assert _regular.member(doc, text), text
    near = [language.outside(random.Random(seed)) for seed in range(100)]
    if expression == "unicode":
        assert near == [None] * 100
    else:
        assert len(set(near)) > 20
        for text in near:
            assert not language.contains(text) and not _regular.member(doc, text), text
            assert sum(not found.has(c) for c in text) == 1


def test_lower_and_upper_are_languages_and_a_near_miss_is_one_character_outside():
    assert LOWER.name == "lower" and UPPER.name == "upper"
    assert LOWER.contains("abc") and not LOWER.contains("abC") and LOWER.contains("")
    assert UPPER.contains("ABC") and not UPPER.contains("AB1")
    assert {LOWER.outside(random.Random(s))[:0] for s in range(5)} == {""}
    outside = "".join(LOWER.outside_pool)
    assert "`" in outside and "{" in outside and "A" in outside and "0" in outside
    for text in ["", "a", "z", "abc", "A", "a1", "é", "a\n"]:
        assert LOWER.contains(text) == (re.fullmatch("[a-z]*", text) is not None)


def test_a_custom_alphabet_is_named_by_its_dotted_path_and_states_its_term():
    from mathema.conjecture import check_conjectures, claim

    assert USERNAME_CHARACTERS.name == "username characters"
    assert USERNAME_CHARACTERS.alphabet.text == 'lower + digit + "_"'
    stated = USERNAME_CHARACTERS.to_json()
    assert stated["definition"] == alphabet_language('"_" + digit + lower').definition()
    one = _regular.term_hash(stated["definition"])
    assert one == _regular.term_hash(alphabet_language('lower + digit + "_"').definition())
    assert one != _regular.term_hash(alphabet_language('lower + digit + "-"').definition())
    assert one == _regular.term_hash(_regular.term(r"[a-z0-9_]*", 0, "matches"))

    def fits(text: str) -> bool:
        return re.fullmatch(r"[a-z0-9_]*", text) is not None

    path = "mathema_language.text.alphabet.USERNAME_CHARACTERS"
    (plain,) = check_conjectures(fits, [claim(f"for text in L[{path}], f(text) == True")])
    assert plain.verdict in ("holds", "proven"), plain.note
    def size(text: str) -> int:
        return len(text)

    (bounded,) = check_conjectures(size, [claim(f"for text in L[{path}, len in [3, 32]], 3 <= f(text) <= 32")])
    assert bounded.verdict in ("holds", "proven"), bounded.note
    (upper,) = check_conjectures(fits, [claim("for text in L[mathema_language.text.alphabet.UPPER], f(text) == True")])
    assert upper.verdict == "falsified"
