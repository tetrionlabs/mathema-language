# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A pattern pictures text one character at a time: `A` a letter, `a` a
lower-case letter, `9` a digit, `X` any character, anything else
itself, `[...]` an optional part, and counts `{n}`, `{n,m}`, `{n+}`.
A pattern that does not read says what was expected and where. Its own
reading, its regular expression and its term agree on every text over a
small alphabet for generated patterns; a letter and a digit are ASCII over
`ascii` and Unicode over `unicode`; members are written directly and
are members, near misses are not; a record field marked with a pattern
holds it, two records deep, in a dataclass, a TypedDict and a pydantic
model."""
import dataclasses
import itertools
import json
import random
import re
import typing

import mathema.languages as languages
import pytest

from mathema_language.text import _regular
from mathema_language.text.pattern import (
    PATTERN,
    Pattern,
    PatternError,
    UnknownSymbol,
    class_ranges,
    pattern_examples,
    pattern_refusal,
    suggest_pattern,
    text_pattern_language,
)

POSTCODE = Pattern("AA99[ ]9AA", "ascii")


@pytest.mark.parametrize("text, inside", {
    "SW19 3AB": True, "SW193AB": True, "sw19 3ab": True, "SW19  3AB": False, "S119 3AB": False,
    "SW19 3A": False, "SW19 3ABC": False, "SW19 3AB\n": False, "": False, "ÉW19 3AB": False,
    "SW١9 3AB": False,
}.items(), ids=repr)
def test_a_postcode_pattern_admits_two_letters_two_digits_an_optional_space_a_digit_two_letters(text, inside):
    assert POSTCODE.matches(text) == inside
    assert (re.fullmatch(POSTCODE.regex, text) is not None) == inside
    assert _regular.member(POSTCODE.term(), text) == inside


@pytest.mark.running_unicode
def test_a_letter_and_a_digit_follow_the_base_language():
    ascii_, unicode_ = Pattern("Aa9X", "ascii"), Pattern("Aa9X")
    assert unicode_.base == "unicode"
    for text, in_ascii, in_unicode in [
            ("Ab1!", True, True), ("Éé٣\n", False, True), ("ab1\x7f", True, True), ("AB1x", False, False),
            ("中é1😀", False, True), ("Ab1é", False, True), ("²b1x", False, False), ("Aǅ1x", False, False),
            ("Ab²x", False, False), ("_b1x", False, False)]:
        assert ascii_.matches(text) == in_ascii, text
        assert unicode_.matches(text) == in_unicode, text
    assert class_ranges("A", "ascii") == ((65, 90), (97, 122))
    assert class_ranges("9", "unicode") == _regular._class_chars(r"\d")
    letters = class_ranges("A", "unicode")
    assert all(chr(c).isalpha() for lo, hi in letters[:50] for c in (lo, hi))
    assert sum(hi - lo + 1 for lo, hi in letters) == sum(chr(c).isalpha() for c in range(0x110000))


@pytest.mark.parametrize("written, canonical", [
    ("AA99[ ]9AA", "AA99[ ]9AA"), ("A{2}9{2,2}", "A{2}9{2}"), ("9{1}", "9"), ("[-9]{0,1}", "[-9]"),
    (r"\-\b\A", "-'bA'"), ("9{0+}a{1+}", "9{0+}a{1+}"), ("[a[9]]{2}", "[a[9]]{2}"), (r"\[\]\{\}\\", r"\[\]\{\}\\"),
    ("9{0,1}", "9{0,1}"), ("'ID'-9{4,6}", "'ID'-9{4,6}"), (" {2}", " {2}"), ("[a]{1}", "[a]{1}"),
])
def test_the_canonical_text_is_the_pattern_as_written_with_needless_marks_dropped(written, canonical):
    shape = Pattern(written, "ascii")
    assert shape.canonical == canonical
    again = Pattern(canonical, "ascii")
    assert again.canonical == canonical and again.regex == shape.regex
    assert _regular.term_hash(again.term()) == _regular.term_hash(shape.term())


@pytest.mark.parametrize("written, position, expected", [
    ("", 0, "at least one symbol or character"),
    ("AA]", 2, 'a symbol, a character or "["'),
    ("A[9", 3, '"]" to close the "[" at position 1'),
    ("A[[9]", 5, '"]" to close the "[" at position 1'),
    ("[]", 1, 'at least one symbol or character inside the "["'),
    ("{2}", 0, "a symbol, a character or a group before a count"),
    ("9{2}{3}", 4, "a symbol, a character or a group before a count"),
    ("9}", 1, "a symbol, a character or a group before a count"),
    ("9{", 1, "a count such as {2}, {2,4} or {2+}"),
    ("9{a}", 1, "a count such as {2}, {2,4} or {2+}"),
    ("9{2,}", 1, "a count such as {2}, {2,4} or {2+}"),
    ("9{-1}", 1, "a count such as {2}, {2,4} or {2+}"),
    ("9{3,2}", 1, "a count from n to m with m at least n and at least 1"),
    ("9{0}", 1, "a count from n to m with m at least n and at least 1"),
    ("AA\\", 3, "a character after the backslash"),
    ("9'ab", 4, "\"'\" to close the quoted text opened at position 1"),
    ("9''9", 2, "at least one character between the quotes"),
    ("'a'" + "'", 4, "\"'\" to close the quoted text opened at position 0"),
])
def test_a_pattern_that_does_not_read_says_what_was_expected_and_where(written, position, expected):
    with pytest.raises(PatternError) as caught:
        Pattern(written, "ascii")
    assert (caught.value.position, caught.value.expected) == (position, expected)
    assert f"expected {expected} at position {position}, found " in str(caught.value)


def test_a_pattern_over_ascii_holds_no_character_outside_it_and_a_base_is_one_of_two():
    with pytest.raises(PatternError) as caught:
        Pattern("A-é", "ascii")
    assert caught.value.position == 2
    assert Pattern("A-'é'").matches("x-é")
    with pytest.raises(ValueError):
        Pattern("A", "latin-1")


def _random_shape(rng: random.Random, depth: int = 0) -> str:
    """A pattern of one to four items drawn from the whole notation."""
    out = []
    for _ in range(rng.randint(1, 4 if depth == 0 else 2)):
        kind = rng.random()
        if kind < 0.2 and depth < 2:
            atom = "[" + _random_shape(rng, depth + 1) + "]"
        elif kind < 0.7:
            atom = rng.choice("Aa9X")
        else:
            atom = rng.choice(["-", "'b'", "\\A", "\\9", " ", "\\[", "'B-'", "'it''s'", "\\'"])
        count = rng.choice(["", "", "", "{2}", "{0,1}", "{1,2}", "{0+}", "{1+}", "{2+}", "{0,2}"])
        out.append(atom + count)
    return "".join(out)


@pytest.mark.running_unicode
@pytest.mark.parametrize("base, alphabet, length", [
    ("ascii", "aB1-A9 [b\n", 3), ("ascii", "aB1-", 5), ("unicode", "aB1-é٣Éǅ²", 3),
], ids=["ascii", "ascii long", "unicode"])
def test_the_reading_the_pattern_and_the_term_agree_on_every_short_text(base, alphabet, length):
    rng = random.Random(21)
    shapes = ["AA99[ ]9AA", "9{0+}", "X{1+}", "[a[9]]{2}", "a{2,3}[-9{1,2}]"]
    shapes += [_random_shape(rng) for _ in range(60 if length <= 3 else 25)]
    texts = ["".join(t) for n in range(length + 1) for t in itertools.product(alphabet, repeat=n)]
    admitted = 0
    for written in shapes:
        shape = Pattern(written, base)
        pinned = shape.term(version=_regular.RUNNING)
        compiled, expression = re.compile(shape.regex), _regular.from_node(pinned["language"])
        assert Pattern(shape.canonical, base).canonical == shape.canonical
        for text in texts:
            own = shape.matches(text)
            admitted += own
            assert (compiled.fullmatch(text) is not None) == own, (written, text)
            assert _regular.holds(expression, text) == own, (written, text)
    assert admitted > 500


@pytest.mark.running_unicode
def test_the_term_is_exact_plain_data_and_is_the_term_of_the_pattern():
    doc = POSTCODE.term()
    assert doc["exact"] is True and doc["kind"] == "regular_language"
    assert doc["source"] == {"dialect": "pattern", "pattern": "AA99[ ]9AA", "base": "ascii", "bindings": {},
                             "unicode": doc["source"]["unicode"]}
    assert json.loads(json.dumps(doc)) == doc
    rng = random.Random(22)
    for written in ["AA99[ ]9AA", "9{0+}", "[a[9]]{2}"] + [_random_shape(rng) for _ in range(40)]:
        for base in ("ascii", "unicode"):
            shape = Pattern(written, base)
            here = _regular.RUNNING
            assert (_regular.term_hash(shape.term(version=here))
                    == _regular.term_hash(_regular.term(shape.regex, 0, "matches", version=here))), written


SHAPES = ["AA99[ ]9AA", "9{0+}", "a{1+}", "X{2}", "[a[9]]{2}", "'ID-'9{4,6}", "A[-A]{0,2}", "9{3}-9{4}",
          "X{0+}", "[a]", "\\A\\9", "a{2,3}[ 9{1,2}]'b'", "'ab'{1,2}9", "'it''s' 9"]


@pytest.mark.running_unicode
@pytest.mark.parametrize("base", ["ascii", "unicode"])
@pytest.mark.parametrize("written", SHAPES)
def test_every_member_written_from_a_pattern_is_a_member_and_every_near_miss_is_not(written, base):
    shape = Pattern(written, base)
    compiled, doc = re.compile(shape.regex), shape.term(version=_regular.RUNNING)
    rng = random.Random(23)
    members = list(shape.members()) + [shape.draw(rng) for _ in range(200)]
    assert len(set(members)) >= 2 or written == "\\A\\9"
    for text in members:
        assert shape.matches(text) and compiled.fullmatch(text) and _regular.member(doc, text), text
    near = list(shape.near_misses()) + [m for seed in range(20) for m in shape.near_misses(random.Random(seed))]
    assert near or written == "X{0+}"
    for text, note in near:
        assert note
        assert not shape.matches(text) and not compiled.fullmatch(text), (text, note)
        assert not _regular.member(doc, text), (text, note)


@pytest.mark.running_unicode
def test_the_members_of_a_pattern_take_both_branches_and_both_ends_of_every_count():
    assert set(Pattern("AA99[ ]9AA", "ascii").members()) >= {"AA000AA", "AA00 0AA", "ZZ00 0ZZ", "zz00 0zz",
                                                           "AA99 9AA"}
    assert set(Pattern("'ID-'9{4,6}", "ascii").members()) >= {"ID-0000", "ID-000000", "ID-9999", "ID-999999"}
    assert set(Pattern("a{1+}[-9]", "ascii").members()) >= {"a", "aaa", "a-0", "aaa-0", "zzz-0"}
    assert set(Pattern("A9").members()) >= {"A0", "É0", "中0", "A٣"}


def test_the_near_misses_of_a_pattern_are_each_one_step_outside_it():
    near = dict(POSTCODE.near_misses())
    assert {"1A000AA": "a character of another class in place of a letter",
            "AAa00AA": "a character of another class in place of a digit",
            "AA00x0AA": 'another character in place of the character " "',
            "AA00  0AA": "an optional part once more than its count allows",
            "AA000AA\n": "a member with a trailing newline",
            "AA000AAA": "a letter once more than its count allows",
            "AA000A": "a letter once fewer than its count allows",
            " AA000AA": "a member after a space"}.items() <= near.items()
    assert "A000AA" in near and "AAA000AA" in near
    assert dict(Pattern("X{2}", "ascii").near_misses()) == {
        "xxx": "any one character once more than its count allows",
        "x": "any one character once fewer than its count allows",
        "xx\n": "a member with a trailing newline", " xx": "a member after a space",
        "\u00e9x": "a character of another class in place of any one character"}
    counted = dict(Pattern("'ID'-9{4,6}[-aa]", "ascii").near_misses())
    assert {"ID-000": "a digit once fewer than its count allows",
            "ID-0000000": "a digit once more than its count allows",
            "ID-0000-a": "an optional part cut one character short"}.items() <= counted.items()


def test_a_pattern_is_a_text_language_whose_draws_are_written_directly():
    language = text_pattern_language("AA99[ ]9AA", "ascii")
    assert language.name == 'ascii, pattern ("AA99[ ]9AA")'
    assert languages.language_problems(language) == []
    assert languages.language_problems(text_pattern_language("A{1+}-9{2}")) == []
    assert language.regex == POSTCODE.regex
    rng = random.Random(24)
    assert all(language.contains(language.sample(rng)) for _ in range(200))
    assert len({language.sample(rng) for _ in range(200)}) > 150
    assert {h.value for h in language.hazards()} >= {"AA000AA", "AA00 0AA", "ZZ00 0ZZ"}
    outside = {language.outside(random.Random(seed)) for seed in range(300)}
    assert all(not language.contains(text) for text in outside) and len(outside) > 50
    assert any(text.endswith("\n") for text in outside) and any("  " in text for text in outside)
    stated = language.to_json()
    assert stated["pattern"] == {"base": "ascii", "pattern": "AA99[ ]9AA", "bindings": {}}
    assert stated["term"] == POSTCODE.term()
    assert text_pattern_language(POSTCODE).name == language.name


# --- a pattern on a record field


@dataclasses.dataclass
class Address:
    postcode: typing.Annotated[str, Pattern("AA99[ ]9AA", "ascii")]
    country: typing.Annotated[str, Pattern("AA", "ascii")] = "GB"


@dataclasses.dataclass
class Customer:
    reference: typing.Annotated[str, Pattern("'ID-'9{4,6}", "ascii")]
    address: Address


@dataclasses.dataclass
class Order:
    customer: Customer
    lines: int = 1


class AddressDict(typing.TypedDict):
    postcode: typing.Annotated[str, Pattern("AA99[ ]9AA", "ascii")]


class CustomerDict(typing.TypedDict):
    address: AddressDict


class OrderDict(typing.TypedDict):
    customer: CustomerDict


def _field_json(stated: dict, *path: str) -> dict:
    """The persisted form of the field reached by `path` through nested
    records, following a `$ref` into the definitions."""
    node = stated
    for name in path:
        node = node["properties"][name]
        if "$ref" in node:
            node = stated["$defs"][node["$ref"].rsplit("/", 1)[-1]]
    return node


def test_a_dataclass_field_two_records_deep_holds_its_pattern():
    from mathema_language.schema.adaptors.dataclass import adapt
    language = adapt(Order)
    assert languages.language_problems(language) == []
    good = Order(Customer("ID-12345", Address("SW19 3AB")))
    assert language.contains(good)
    assert not language.contains(Order(Customer("ID-12345", Address("SW19  3AB"))))
    assert not language.contains(Order(Customer("ID-123", Address("SW19 3AB"))))
    assert not language.contains(Order(Customer("ID-12345", Address("SW19 3AB", "gbr"))))
    assert "postcode" in str(language.explain(Order(Customer("ID-12345", Address("SW19 3AB\n")))))
    rng = random.Random(25)
    drawn = [language.sample(rng) for _ in range(60)]
    assert all(language.contains(row) for row in drawn)
    assert all(POSTCODE.matches(row.customer.address.postcode) for row in drawn)
    assert len({row.customer.address.postcode for row in drawn}) > 30
    field = _field_json(language.to_json(), "customer", "address", "postcode")
    assert field["pattern"] == POSTCODE.regex
    assert field["x-mathema"]["pattern"] == {"base": "ascii", "pattern": "AA99[ ]9AA", "bindings": {}}
    assert field["x-mathema"]["term"] == POSTCODE.term()


def test_a_typeddict_key_two_records_deep_holds_its_pattern():
    from mathema_language.schema.adaptors.typeddict import adapt
    language = adapt(OrderDict)
    assert languages.language_problems(language) == []
    assert language.contains({"customer": {"address": {"postcode": "SW193AB"}}})
    assert not language.contains({"customer": {"address": {"postcode": "SW193A"}}})
    rng = random.Random(26)
    drawn = [language.sample(rng) for _ in range(40)]
    assert all(language.contains(row) and POSTCODE.matches(row["customer"]["address"]["postcode"])
               for row in drawn)
    field = _field_json(language.to_json(), "customer", "address", "postcode")
    assert field["x-mathema"]["term"] == POSTCODE.term()


def test_a_pydantic_field_two_models_deep_holds_its_pattern_and_the_model_validates_it():
    pydantic = pytest.importorskip("pydantic")
    from mathema_language.schema.adaptors.pydantic import adapt

    class AddressModel(pydantic.BaseModel):
        postcode: typing.Annotated[str, Pattern("AA99[ ]9AA", "ascii")]

    class CustomerModel(pydantic.BaseModel):
        address: AddressModel

    class OrderModel(pydantic.BaseModel):
        customer: CustomerModel

    assert AddressModel(postcode="SW19 3AB").postcode == "SW19 3AB"
    with pytest.raises(pydantic.ValidationError):
        AddressModel(postcode="SW19 3AB\n")
    language = adapt(OrderModel)
    assert languages.language_problems(language) == []
    def order(postcode: str) -> OrderModel:
        address = AddressModel.model_construct(postcode=postcode)
        return OrderModel.model_construct(customer=CustomerModel.model_construct(address=address))

    assert language.contains(order("SW193AB"))
    assert not language.contains(order("SW19  3AB")) and not language.contains(order("SW193AB\n"))
    rng = random.Random(27)
    drawn = [language.sample(rng) for _ in range(40)]
    assert all(language.contains(row) for row in drawn)
    assert all(POSTCODE.matches(row.customer.address.postcode) for row in drawn)
    field = _field_json(language.to_json(), "customer", "address", "postcode")
    assert field["x-mathema"]["term"] == POSTCODE.term()


def test_a_plain_pattern_on_a_dataclass_field_is_still_refused():
    from mathema_language.schema.adaptors.dataclass import schema_of

    class Pattern:
        pattern = "[a-z]+"

    @dataclasses.dataclass
    class Tagged:
        tag: typing.Annotated[str, Pattern()]

    with pytest.raises(ValueError):
        schema_of(Tagged)


# --- the word's own description


def test_every_example_reads_and_names_a_language():
    assert pattern_examples() == {"ascii": 'L[ascii, pattern ("AA99[ ]9AA")]',
                                "unicode": 'L[unicode, pattern ("AA-9{4}")]'}
    for base, kind in PATTERN.items():
        assert pattern_refusal(base, kind.example) is None
        language = text_pattern_language(*kind.example, base)
        assert "L[" + language.name + "]" == pattern_examples()[base]
        assert languages.resolve_language(base).name == base


@pytest.mark.parametrize("base, arguments, said", [
    ("iso_date", ("9999-99-99",), "'pattern' has no meaning for L[iso_date]: it pictures text in L[ascii] "
                                  "or L[unicode]"),
    ("ascii", ("AA", "99"), "takes one argument, the picture, not 2"),
    ("ascii", ("AA[9",), 'does not read on L[ascii]: pattern \'AA[9\': expected "]" to close the "[" at '
                         "position 2 at position 4, found the end of the pattern"),
    ("ascii", ("é",), "expected an ASCII character in a pattern over ascii at position 0"),
])
def test_a_refusal_says_what_the_word_expects(base, arguments, said):
    assert said in pattern_refusal(base, arguments)


@pytest.mark.parametrize("base, arguments, suggested", [
    ("iso_date", ("9999-99-99",), ('L[ascii, pattern ("9999-99-99")]', 'L[unicode, pattern ("9999-99-99")]')),
    ("ascii", ("A-é",), ("L[unicode, pattern (\"A-'é'\")]",)),
    ("ascii", ("[a-z",), ('L[ascii, pattern ("AA99[ ]9AA")]',)),
    ("ascii", ("[a-z]+(",), ("L[ascii, pattern (\"[a-'z']+(\")]",)),
    ("ascii", ("KEY-99",), ("L[ascii, pattern (\"'KEY'-99\")]",)),
    ("json", ("ID-9999",), ("L[ascii, pattern (\"'ID'-9999\")]", "L[unicode, pattern (\"'ID'-9999\")]")),
    ("unicode", ("[a-z]{2,}",), ('L[unicode, matches (re(r"[a-z]{2,}", python))]',)),
    ("ascii", ("AA", "99"), ('L[ascii, pattern ("AA99[ ]9AA")]',)),
    ("json", ("[",), ('L[ascii, pattern ("AA99[ ]9AA")]',)),
    ("ascii", ("AA99",), ()),
])
def test_a_refused_use_suggests_the_claim_that_was_meant(base, arguments, suggested):
    assert suggest_pattern(base, arguments) == suggested
    for text in suggested:
        if ", pattern (" in text:
            name = text[2:text.index(",")]
            picture = text[text.index('("') + 2:text.rindex('")')]
            assert pattern_refusal(name, (picture,)) is None


# --- letters and digits are symbols; literal text is quoted; symbols are bound to alphabets


@pytest.mark.parametrize("written, said", [
    ("KEY-99", "K, E and Y are not symbols. For the literal text write 'KEY': pattern (\"'KEY'-99\"). "
               "To use K as a symbol, bind it: pattern (\"KEY-99\", K = ...)"),
    ("ID-9999", "I and D are not symbols. For the literal text write 'ID': pattern (\"'ID'-9999\"). "
                "To use I as a symbol, bind it: pattern (\"ID-9999\", I = ...)"),
    ("9b", "b is not a symbol. For the literal text write 'b': pattern (\"9'b'\"). "
           "To use b as a symbol, bind it: pattern (\"9b\", b = ...)"),
    ("AB-12-B", "B, 1 and 2 are not symbols. For the literal text write 'B' and '12': "
                "pattern (\"A'B'-'12'-'B'\"). To use B as a symbol, bind it: pattern (\"AB-12-B\", B = ...)"),
    ("9é", "é is not a symbol. For the literal text write 'é': pattern (\"9'é'\"). "
           "To use é as a symbol, bind it: pattern (\"9é\", é = ...)"),
])
def test_a_letter_or_digit_that_is_no_symbol_is_refused_with_both_ways_to_mend_it(written, said):
    with pytest.raises(UnknownSymbol) as caught:
        Pattern(written)
    assert str(caught.value) == said
    assert isinstance(caught.value, PatternError) and caught.value.position == written.index(caught.value.symbols[0])
    mended = Pattern(caught.value.quoted)
    assert mended.canonical == caught.value.quoted


def test_the_refusal_keeps_the_bindings_that_were_given():
    with pytest.raises(UnknownSymbol) as caught:
        Pattern("KEY-U9", "ascii", U="upper")
    assert str(caught.value) == (
        "K, E and Y are not symbols. For the literal text write 'KEY': pattern (\"'KEY'-U9\", U = upper). "
        "To use K as a symbol, bind it: pattern (\"KEY-U9\", U = upper, K = ...)")
    assert pattern_refusal("ascii", ("KEY-U9",), {"U": "upper"}) == str(caught.value)
    assert suggest_pattern("ascii", ("KEY-U9",), {"U": "upper"}) == (
        "L[ascii, pattern (\"'KEY'-U9\", U = upper)]",)


@pytest.mark.parametrize("written, canonical, member, not_member", [
    ("'INV-'9{4}", "'INV-'9{4}", "INV-2026", "inv-2026"), ("'-'9", "-9", "-1", "'-'1"),
    (r"\K\E\Y-99", "'KEY'-99", "KEY-12", "KEX-12"), ("'ab'{2}9", "'ab'{2}9", "abab1", "ab1"),
    ("'--'{2}", "'--'{2}", "----", "---"), ("'-'{2}", "-{2}", "--", "-"), ("'it''s'9", "'it''s'9", "it's1", "its1"),
    (r"\'9\'", r"\'9\'", "'1'", "1"), (r"\K{2}'ab'", r"\K{2}'ab'", "KKab", "Kab"),
    (r"\K'EE'{2}", r"\K'EE'{2}", "KEEEE", "KEE"), ("'[]'", r"\[\]", "[]", ""), ("' 'A' '", " A ", " x ", "x"),
    (r"'A'\9'X'", "'A9X'", "A9X", "B1Y"), ("['ID']9", "['ID']9", "ID1", "I1"),
])
def test_literal_text_is_quoted_and_the_canonical_picture_quotes_only_letters_and_digits(
        written, canonical, member, not_member):
    shape = Pattern(written, "ascii")
    assert shape.canonical == canonical
    again = Pattern(canonical, "ascii")
    assert again.canonical == canonical and again.regex == shape.regex
    for reading in (shape.matches, lambda t: re.fullmatch(shape.regex, t) is not None,
                    lambda t: _regular.member(shape.term(), t)):
        assert reading(member) and not reading(not_member)


def test_a_symbol_is_bound_to_an_alphabet_after_the_picture():
    from mathema_language.text.alphabets import alphabet

    word = Pattern("AW{0+}", "ascii", W='alnum + "_"')
    assert word.arguments == '"AW{0+}", W = alnum + "_"'
    assert word.matches("a_1") and word.matches("Z") and not word.matches("_a") and not word.matches("a-")
    hexes = Pattern("HH:HH:HH", "ascii", H="hexdigit")
    assert hexes.matches("0a:FF:9c") and not hexes.matches("0g:FF:9c")
    key = Pattern("'KEY-'U{3}9{4}", "ascii", U="upper")
    assert key.arguments == "\"'KEY-'U{3}9{4}\", U = upper"
    assert key.matches("KEY-ABC1234") and not key.matches("KEY-abc1234")
    assert Pattern("AW{0+}", "ascii", W=alphabet("alnum") + "_") == word
    other = Pattern("AW{0+}", "ascii", bindings={"W": '"_" + alnum'})
    assert other == word and hash(word) == hash(other)
    assert word != Pattern("AW{0+}", "ascii", W="alnum")
    assert eval(repr(word), {"Pattern": Pattern}) == word
    language = text_pattern_language("AW{0+}", "ascii", {"W": 'alnum + "_"'})
    assert language.name == 'ascii, pattern ("AW{0+}", W = alnum + "_")'
    assert languages.language_problems(language) == []
    assert language.to_json()["pattern"] == {"base": "ascii", "pattern": "AW{0+}", "bindings": {"W": 'alnum + "_"'}}
    assert word.term()["source"]["bindings"] == {"W": 'alnum + "_"'}


def test_a_binding_may_give_a_built_in_symbol_another_alphabet_and_is_written_after_the_picture():
    upper = Pattern("AA99", "ascii", A="upper")
    assert upper.arguments == '"AA99", A = upper'
    assert upper.matches("AB12") and not upper.matches("ab12") and Pattern("AA99", "ascii").matches("ab12")
    clock = Pattern("99:99", "ascii", bindings={"9": "hexdigit"})
    assert clock.arguments == '"99:99", 9 = hexdigit'
    assert clock.matches("ff:0A") and not Pattern("99:99", "ascii").matches("ff:0A")
    assert eval(repr(clock), {"Pattern": Pattern}) == clock
    both = Pattern("ZA9", "ascii", bindings={"9": "hexdigit", "Z": "upper", "A": 'lower + "_"'})
    assert both.arguments == '"ZA9", 9 = hexdigit, A = lower + "_", Z = upper'
    assert both.matches("Q_f") and not both.matches("q_f")


@pytest.mark.running_unicode
@pytest.mark.parametrize("build, error, said", [
    (lambda: Pattern("AA", "ascii", W="upper"), PatternError, "expected the bound symbol W somewhere in the picture"),
    (lambda: Pattern("'W'9", "ascii", W="upper"), PatternError, "expected the bound symbol W somewhere in the picture"),
    (lambda: Pattern("AW", "ascii", W="uper"), ValueError, "did you mean upper?"),
    (lambda: Pattern("AW", "ascii", W="unicode_alpha"), ValueError, "holds a character outside ASCII"),
    (lambda: Pattern("AW", "ascii", bindings={"WW": "upper"}), ValueError, "a bound symbol is one letter or digit"),
    (lambda: Pattern("A-", "ascii", bindings={"-": "upper"}), ValueError, "a bound symbol is one letter or digit"),
    (lambda: Pattern("AW", "ascii", W=3), ValueError, "an alphabet is an alphabet expression"),
])
def test_a_binding_that_is_unused_or_does_not_read_is_refused(build, error, said):
    with pytest.raises(error) as caught:
        build()
    assert said in str(caught.value)
    assert Pattern("AW", "unicode", W="unicode_alpha").matches("xé")


BOUND = [("AW{0+}", {"W": 'alnum + "_"'}), ("HH[:HH]{0,2}", {"H": "hexdigit"}), ("'KEY-'U{3}9{4}", {"U": "upper"}),
         ("AA99", {"A": "upper"}), ("99:99", {"9": "hexdigit"}), ("S{1+}[.S{1+}]", {"S": 'lower + digit + "-"'}),
         ("QX", {"Q": '"a" + "b"'})]


@pytest.mark.parametrize("written, bindings", BOUND, ids=[b[0] for b in BOUND])
def test_a_bound_pattern_agrees_three_ways_and_writes_members_and_near_misses(written, bindings):
    shape = Pattern(written, "ascii", bindings)
    compiled, doc = re.compile(shape.regex), shape.term()
    assert _regular.term_hash(doc) == _regular.term_hash(_regular.term(shape.regex, 0, "matches"))
    rng = random.Random(28)
    members = list(shape.members()) + [shape.draw(rng) for _ in range(200)]
    assert len(set(members)) > 5
    for text in members:
        assert shape.matches(text) and compiled.fullmatch(text) and _regular.member(doc, text), text
    near = list(shape.near_misses()) + [m for seed in range(20) for m in shape.near_misses(random.Random(seed))]
    assert any("another class" in note for _, note in near)
    for text, _note in near:
        assert not shape.matches(text) and not compiled.fullmatch(text) and not _regular.member(doc, text), text
    for n in range(4):
        for letters in itertools.product("aB1-_:.fGK", repeat=n):
            text = "".join(letters)
            assert shape.matches(text) == (compiled.fullmatch(text) is not None), text


def test_the_reading_of_a_pattern_names_a_bound_symbol_by_its_alphabet():
    assert Pattern("AW{0+}", "ascii", W='alnum + "_"').explain() == (
        'one of: ASCII letters; then any number of: alnum + "_"')
    assert Pattern("HH:HH", "ascii", H="hexdigit").explain() == 'exactly 2 of: hexdigit; then ":"; then exactly 2 of: hexdigit'
    assert Pattern("'KEY-'U{3}9{4}", "ascii", U="upper").explain() == (
        '"KEY-"; then exactly 3 of: upper; then exactly 4 of: 0-9')
    assert Pattern("AA99", "ascii", A="upper").explain() == "exactly 2 of: upper; then exactly 2 of: 0-9"
    assert Pattern("AA99", "ascii").explain() == "exactly 2 of: ASCII letters; then exactly 2 of: 0-9"


def test_a_bound_pattern_marks_a_record_field():
    from mathema_language.schema.adaptors.dataclass import adapt

    @dataclasses.dataclass
    class Account:
        name: typing.Annotated[str, Pattern("AW{2,31}", "ascii", W='lower + digit + "_"', A="lower")]

    language = adapt(Account)
    assert language.contains(Account("a_1")) and not language.contains(Account("A_1"))
    assert not language.contains(Account("a_"))
    rng = random.Random(29)
    assert all(language.contains(language.sample(rng)) for _ in range(40))
    field = language.to_json()["properties"]["name"]["x-mathema"]
    assert field["pattern"] == {"base": "ascii", "pattern": "AW{2,31}",
                              "bindings": {"A": "lower", "W": 'lower + digit + "_"'}}
