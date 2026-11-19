# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A shape pictures text one character at a time: `A` a letter, `a` a
lower-case letter, `9` a digit, `X` any character, anything else
itself, `[...]` an optional part, and counts `{n}`, `{n,m}`, `{n+}`.
A shape that does not read says what was expected and where. Its own
reading, its regular expression and its term agree on every text over a
small alphabet for generated shapes; a letter and a digit are ASCII over
`ascii` and Unicode over `unicode`; members are written directly and
are members, near misses are not; a record field marked with a shape
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
from mathema_language.text.shape import (
    SHAPE,
    Shape,
    ShapeError,
    claim_text,
    class_ranges,
    shape_examples,
    shape_language,
    shape_refusal,
    suggest_shape,
)

POSTCODE = Shape("AA99[ ]9AA", "ascii")


@pytest.mark.parametrize("text, inside", {
    "SW19 3AB": True, "SW193AB": True, "sw19 3ab": True, "SW19  3AB": False, "S119 3AB": False,
    "SW19 3A": False, "SW19 3ABC": False, "SW19 3AB\n": False, "": False, "ÉW19 3AB": False,
    "SW١9 3AB": False,
}.items(), ids=repr)
def test_a_postcode_shape_admits_two_letters_two_digits_an_optional_space_a_digit_two_letters(text, inside):
    assert POSTCODE.matches(text) == inside
    assert (re.fullmatch(POSTCODE.pattern, text) is not None) == inside
    assert _regular.member(POSTCODE.term(), text) == inside


def test_a_letter_and_a_digit_follow_the_base_language():
    ascii_, unicode_ = Shape("Aa9X", "ascii"), Shape("Aa9X")
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
    (r"\-\b\A", r"-b\A"), ("9{0+}a{1+}", "9{0+}a{1+}"), ("[a[9]]{2}", "[a[9]]{2}"), (r"\[\]\{\}\\", r"\[\]\{\}\\"),
    ("9{0,1}", "9{0,1}"), ("ID-9{4,6}", "ID-9{4,6}"), (" {2}", " {2}"), ("[a]{1}", "[a]{1}"),
])
def test_the_canonical_text_is_the_shape_as_written_with_needless_marks_dropped(written, canonical):
    shape = Shape(written, "ascii")
    assert shape.shape == canonical
    again = Shape(canonical, "ascii")
    assert again.shape == canonical and again.pattern == shape.pattern
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
])
def test_a_shape_that_does_not_read_says_what_was_expected_and_where(written, position, expected):
    with pytest.raises(ShapeError) as caught:
        Shape(written, "ascii")
    assert (caught.value.position, caught.value.expected) == (position, expected)
    assert f"expected {expected} at position {position}, found " in str(caught.value)


def test_a_shape_over_ascii_holds_no_character_outside_it_and_a_base_is_one_of_two():
    with pytest.raises(ShapeError) as caught:
        Shape("A-é", "ascii")
    assert caught.value.position == 2
    assert Shape("A-é").matches("x-é")
    with pytest.raises(ValueError):
        Shape("A", "latin-1")


def _random_shape(rng: random.Random, depth: int = 0) -> str:
    """A shape of one to four items drawn from the whole notation."""
    out = []
    for _ in range(rng.randint(1, 4 if depth == 0 else 2)):
        kind = rng.random()
        if kind < 0.2 and depth < 2:
            atom = "[" + _random_shape(rng, depth + 1) + "]"
        elif kind < 0.7:
            atom = rng.choice("Aa9X")
        else:
            atom = rng.choice(["-", "b", "\\A", "\\9", " ", "\\[", "B"])
        count = rng.choice(["", "", "", "{2}", "{0,1}", "{1,2}", "{0+}", "{1+}", "{2+}", "{0,2}"])
        out.append(atom + count)
    return "".join(out)


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
        shape = Shape(written, base)
        compiled, expression = re.compile(shape.pattern), _regular.from_node(shape.term()["language"])
        assert Shape(shape.shape, base).shape == shape.shape
        for text in texts:
            own = shape.matches(text)
            admitted += own
            assert (compiled.fullmatch(text) is not None) == own, (written, text)
            assert _regular.holds(expression, text) == own, (written, text)
    assert admitted > 500


def test_the_term_is_exact_plain_data_and_is_the_term_of_the_pattern():
    doc = POSTCODE.term()
    assert doc["exact"] is True and doc["kind"] == "regular_language"
    assert doc["source"] == {"dialect": "shape", "shape": "AA99[ ]9AA", "base": "ascii",
                             "unicode": doc["source"]["unicode"]}
    assert json.loads(json.dumps(doc)) == doc
    rng = random.Random(22)
    for written in ["AA99[ ]9AA", "9{0+}", "[a[9]]{2}"] + [_random_shape(rng) for _ in range(40)]:
        for base in ("ascii", "unicode"):
            shape = Shape(written, base)
            assert (_regular.term_hash(shape.term())
                    == _regular.term_hash(_regular.term(shape.pattern, 0, "matches"))), written


SHAPES = ["AA99[ ]9AA", "9{0+}", "a{1+}", "X{2}", "[a[9]]{2}", "ID-9{4,6}", "A[-A]{0,2}", "9{3}-9{4}",
          "X{0+}", "[a]", "\\A\\9", "a{2,3}[ 9{1,2}]b"]


@pytest.mark.parametrize("base", ["ascii", "unicode"])
@pytest.mark.parametrize("written", SHAPES)
def test_every_member_written_from_a_shape_is_a_member_and_every_near_miss_is_not(written, base):
    shape = Shape(written, base)
    compiled, doc = re.compile(shape.pattern), shape.term()
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


def test_the_members_of_a_shape_take_both_branches_and_both_ends_of_every_count():
    assert set(Shape("AA99[ ]9AA", "ascii").members()) >= {"AA000AA", "AA00 0AA", "ZZ00 0ZZ", "zz00 0zz",
                                                           "AA99 9AA"}
    assert set(Shape("ID-9{4,6}", "ascii").members()) >= {"ID-0000", "ID-000000", "ID-9999", "ID-999999"}
    assert set(Shape("a{1+}[-9]", "ascii").members()) >= {"a", "aaa", "a-0", "aaa-0", "zzz-0"}
    assert set(Shape("A9").members()) >= {"A0", "É0", "中0", "A٣"}


def test_the_near_misses_of_a_shape_are_each_one_step_outside_it():
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
    assert dict(Shape("X{2}", "ascii").near_misses()) == {
        "xxx": "any one character once more than its count allows",
        "x": "any one character once fewer than its count allows",
        "xx\n": "a member with a trailing newline", " xx": "a member after a space"}
    counted = dict(Shape("ID-9{4,6}[-aa]", "ascii").near_misses())
    assert {"ID-000": "a digit once fewer than its count allows",
            "ID-0000000": "a digit once more than its count allows",
            "ID-0000-a": "an optional part cut one character short"}.items() <= counted.items()


def test_a_shape_is_a_text_language_whose_draws_are_written_directly():
    language = shape_language("AA99[ ]9AA", "ascii")
    assert language.name == 'ascii, shape ("AA99[ ]9AA")'
    assert languages.language_problems(language) == []
    assert languages.language_problems(shape_language("A{1+}-9{2}")) == []
    assert language.pattern == POSTCODE.pattern
    rng = random.Random(24)
    assert all(language.contains(language.sample(rng)) for _ in range(200))
    assert len({language.sample(rng) for _ in range(200)}) > 150
    assert {h.value for h in language.hazards()} >= {"AA000AA", "AA00 0AA", "ZZ00 0ZZ"}
    outside = {language.outside(random.Random(seed)) for seed in range(300)}
    assert all(not language.contains(text) for text in outside) and len(outside) > 50
    assert any(text.endswith("\n") for text in outside) and any("  " in text for text in outside)
    stated = language.to_json()
    assert stated["shape"] == {"base": "ascii", "shape": "AA99[ ]9AA"}
    assert stated["definition"] == POSTCODE.term()
    assert shape_language(POSTCODE).name == language.name


# --- a shape on a record field


@dataclasses.dataclass
class Address:
    postcode: typing.Annotated[str, Shape("AA99[ ]9AA", "ascii")]
    country: typing.Annotated[str, Shape("AA", "ascii")] = "GB"


@dataclasses.dataclass
class Customer:
    reference: typing.Annotated[str, Shape("ID-9{4,6}", "ascii")]
    address: Address


@dataclasses.dataclass
class Order:
    customer: Customer
    lines: int = 1


class AddressDict(typing.TypedDict):
    postcode: typing.Annotated[str, Shape("AA99[ ]9AA", "ascii")]


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


def test_a_dataclass_field_two_records_deep_holds_its_shape():
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
    assert field["pattern"] == POSTCODE.pattern
    assert field["x-mathema"]["shape"] == {"base": "ascii", "shape": "AA99[ ]9AA"}
    assert field["x-mathema"]["definition"] == POSTCODE.term()


def test_a_typeddict_key_two_records_deep_holds_its_shape():
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
    assert field["x-mathema"]["definition"] == POSTCODE.term()


def test_a_pydantic_field_two_models_deep_holds_its_shape_and_the_model_validates_it():
    pydantic = pytest.importorskip("pydantic")
    from mathema_language.schema.adaptors.pydantic import adapt

    class AddressModel(pydantic.BaseModel):
        postcode: typing.Annotated[str, Shape("AA99[ ]9AA", "ascii")]

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
    assert field["x-mathema"]["definition"] == POSTCODE.term()


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
    assert shape_examples() == {"ascii": 'L[ascii, shape ("AA99[ ]9AA")]',
                                "unicode": 'L[unicode, shape ("AA-9{4}")]'}
    for base, kind in SHAPE.items():
        assert shape_refusal(base, kind.example) is None
        language = shape_language(*kind.example, base)
        assert "L[" + language.name + "]" == shape_examples()[base]
        assert languages.resolve_language(base).name == base


@pytest.mark.parametrize("base, arguments, said", [
    ("iso_date", ("9999-99-99",), "'shape' has no meaning for L[iso_date]: it pictures text in L[ascii] "
                                  "or L[unicode]"),
    ("ascii", ("AA", "99"), "takes one argument, the picture, not 2"),
    ("ascii", ("AA[9",), 'does not read on L[ascii]: shape \'AA[9\': expected "]" to close the "[" at '
                         "position 2 at position 4, found the end of the shape"),
    ("ascii", ("é",), "expected an ASCII character in a shape over ascii at position 0"),
])
def test_a_refusal_says_what_the_word_expects(base, arguments, said):
    assert said in shape_refusal(base, arguments)


@pytest.mark.parametrize("base, arguments, suggested", [
    ("iso_date", ("9999-99-99",), ('L[ascii, shape ("9999-99-99")]', 'L[unicode, shape ("9999-99-99")]')),
    ("ascii", ("A-é",), ('L[unicode, shape ("A-é")]',)),
    ("ascii", ("[a-z",), ('L[ascii, shape ("AA99[ ]9AA")]',)),
    ("ascii", ("[a-z]+(",), ()),
    ("unicode", ("[a-z]{2,}",), ('L[unicode, matches (re(r"[a-z]{2,}", python))]',)),
    ("ascii", ("AA", "99"), ('L[ascii, shape ("AA99[ ]9AA")]',)),
    ("json", ("[",), ('L[ascii, shape ("AA99[ ]9AA")]',)),
    ("ascii", ("AA99",), ()),
])
def test_a_refused_use_suggests_the_claim_that_was_meant(base, arguments, suggested):
    assert suggest_shape(base, arguments) == suggested
    for text in suggested:
        if ", shape (" in text:
            name = text[2:text.index(",")]
            argument = arguments if text == claim_text(name, "shape", arguments) else SHAPE[name].example
            assert shape_refusal(name, argument) is None
