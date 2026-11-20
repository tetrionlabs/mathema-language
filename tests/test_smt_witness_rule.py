# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Which witness an inclusion reports: among the records both validations
confirm, each text field in turn takes the shortest text, and then,
character by character, a letter before a digit before other printable
ASCII before any other character, the lower code point within each.
Fields that are not text keep the value the solver gave."""
import pytest

z3 = pytest.importorskip("z3")
pytest.importorskip("jsonschema")

from mathema_language import smt  # noqa: E402
from mathema_language.schema.adaptors import adapt_row  # noqa: E402


def schema(required=("s",), **properties):
    return {"type": "object", "required": list(required), "properties": properties}


def text(**constraints):
    return {"type": "string", **constraints}


NEEDS_T = dict(required=("s", "t"), t=text())


def witness(older, newer):
    result = smt._schema_inclusion(older, newer)
    assert result.verdict == "falsified", str(result)
    assert smt._admits(adapt_row(older), result.witness)
    assert not smt._admits(adapt_row(newer), result.witness)
    return result.witness


def test_the_first_letter_where_any_one_character_will_do():
    assert witness(schema(s=text(minLength=1)), schema(s=text(minLength=1), **NEEDS_T)) == {"s": "A"}


def test_the_empty_string_where_it_is_a_witness():
    assert witness(schema(s=text()), schema(s=text(minLength=1))) == {"s": ""}
    assert witness(schema(s=text(maxLength=5)), schema(s=text(pattern="^.+$"))) == {"s": ""}


def test_the_shortest_before_the_most_readable():
    # "!" alone is shorter than any text with a letter
    older = schema(s=text(pattern="^(?:!|[a-z]{2})$"))
    assert witness(older, schema(s=text(pattern="^(?:!|[a-z]{2})$"), **NEEDS_T)) == {"s": "!"}


@pytest.mark.parametrize("pattern, expected", [
    (r"^[b1][a!]$", "ba"),            # a letter before a digit, a letter before punctuation
    (r"^[1!][\x7f ]$", "1 "),         # a digit before punctuation, printable before the rest
    (r"^[zy][0-9]$", "y0"),           # the lower code point within a rank
    (r"^[!#][~{]$", "!{"),
    (r"^[aB][bA]$", "BA"),            # capitals come first among letters, by code point
])
def test_character_by_character_by_rank_then_code_point(pattern, expected):
    older = schema(s=text(pattern=pattern))
    assert witness(older, schema(s=text(pattern=pattern), **NEEDS_T)) == {"s": expected}


def test_the_lowest_code_point_where_no_printable_text_is_a_witness():
    pattern = "^[\\x01-\\x05\\x7f]+$"
    older = schema(s=text(pattern=pattern))
    assert witness(older, schema(s=text(pattern=pattern), **NEEDS_T)) == {"s": "\x01"}
    wide = "^[\\u00e9\\u0100]$"
    assert witness(schema(s=text(pattern=wide)), schema(s=text(pattern=wide), **NEEDS_T)) == {"s": "é"}


def test_a_field_that_is_not_text_keeps_a_value_that_falsifies():
    older = schema(required=("n", "s"), n={"type": "integer", "minimum": 0, "maximum": 10},
                   s=text(minLength=2))
    newer = schema(required=("n", "s"), n={"type": "integer", "minimum": 0, "maximum": 5},
                   s=text(minLength=2))
    found = witness(older, newer)
    assert found["s"] == "AA" and isinstance(found["n"], int) and 5 < found["n"] <= 10


def test_each_text_field_in_turn():
    older = schema(required=("s", "u"), s=text(minLength=1), u=text(pattern="^[0-9]{2}$"))
    newer = schema(required=("s", "u", "t"), s=text(minLength=1), u=text(pattern="^[0-9]{2}$"), t=text())
    assert witness(older, newer) == {"s": "A", "u": "00"}


def test_the_verdict_does_not_wait_on_the_search(monkeypatch):
    older, newer = schema(s=text(minLength=1)), schema(s=text(minLength=1), **NEEDS_T)
    monkeypatch.setattr(smt, "_WITNESS_SECONDS", 0.0)
    result = smt._schema_inclusion(older, newer)
    assert result.verdict == "falsified"
    assert smt._admits(adapt_row(older), result.witness)
    assert not smt._admits(adapt_row(newer), result.witness)
