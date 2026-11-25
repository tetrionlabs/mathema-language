# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Text a schema library refuses whatever the field says: pydantic does
not take a `str` holding a surrogate code point once the field has a
length, a pattern or the model a `str_` setting (it encodes the text to
check it), while a bare pydantic `str`, a JSON Schema string, a dataclass
or TypedDict field and an argparse value all take one. The side of the
encoding that admits at most what the library admits must leave such
text out, so an inclusion into a constrained pydantic string is not
proven while a surrogate string is its counterexample."""
import argparse
import dataclasses
import typing

import pytest

z3 = pytest.importorskip("z3")
pydantic = pytest.importorskip("pydantic")
pytest.importorskip("jsonschema")

from mathema_language import smt  # noqa: E402
from mathema_language.schema.adaptors import adapt_row  # noqa: E402

LONE = "\ud800"
JSON_TEXT = {"type": "object", "required": ["s"], "properties": {"s": {"type": "string"}}}
JSON_SHORT = {"type": "object", "required": ["s"],
              "properties": {"s": {"type": "string", "maxLength": 9}}}
JSON_FILLED = {"type": "object", "required": ["s"],
               "properties": {"s": {"type": "string", "minLength": 1}}}


class Bare(pydantic.BaseModel):
    s: str


class Short(pydantic.BaseModel):
    s: str = pydantic.Field(max_length=9)


class Filled(pydantic.BaseModel):
    s: str = pydantic.Field(min_length=1)


class Matched(pydantic.BaseModel):
    s: str = pydantic.Field(pattern="^[^a]*$")


class Stripped(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(str_strip_whitespace=True)
    s: str


class Inner(pydantic.BaseModel):
    s: str = pydantic.Field(max_length=9)


class Outer(pydantic.BaseModel):
    inner: Inner


@dataclasses.dataclass
class Plain:
    s: str


class Typed(typing.TypedDict):
    s: str


def test_which_libraries_take_a_surrogate():
    assert smt._admits(adapt_row(JSON_TEXT), {"s": LONE})
    assert smt._admits(adapt_row(JSON_SHORT), {"s": LONE})
    assert smt._admits(adapt_row(Plain), {"s": LONE})
    assert smt._admits(adapt_row(Typed), {"s": LONE})
    parser = argparse.ArgumentParser()
    parser.add_argument("--s", default="x")
    assert parser.parse_args(["--s", LONE]).s == LONE
    assert smt._admits(adapt_row(Bare), {"s": LONE})
    for model in (Short, Filled, Matched, Stripped):
        assert not smt._admits(adapt_row(model), {"s": LONE}), model.__name__


@pytest.mark.parametrize("older, newer, counterexample", [
    (JSON_SHORT, Short, {"s": LONE}),
    (JSON_SHORT, Short, {"s": "a" + LONE + "b"}),
    (JSON_FILLED, Filled, {"s": LONE}),
    ({"type": "object", "required": ["s"], "properties": {"s": {"type": "string", "pattern": "^[^a]*$"}}},
     Matched, {"s": LONE}),
    ({"type": "object", "required": ["inner"], "properties": {"inner": JSON_SHORT}}, Outer,
     {"inner": {"s": LONE}}),
    (Bare, Short, {"s": LONE}),
])
def test_an_inclusion_into_a_constrained_pydantic_string_is_not_proven(older, newer, counterexample):
    assert smt._admits(adapt_row(older), counterexample)
    assert not smt._admits(adapt_row(newer), counterexample)
    result = smt._schema_inclusion(older, newer)
    assert result.verdict != "proven", str(result)


def test_an_inclusion_into_a_model_with_a_str_setting_is_not_proven():
    result = smt._schema_inclusion(JSON_TEXT, Stripped)
    assert result.verdict != "proven", str(result)


@pytest.mark.parametrize("older, newer", [(Short, JSON_SHORT), (Short, Short), (JSON_TEXT, Bare),
                                          (Bare, JSON_TEXT),
                                          (Plain, JSON_TEXT), (Short, Bare), (Filled, JSON_FILLED)])
def test_inclusions_that_hold_are_still_proven(older, newer):
    assert smt._schema_inclusion(older, newer).verdict == "proven"


@pytest.mark.parametrize("newer", [Plain, Typed])
def test_an_open_object_is_not_included_in_a_class_that_refuses_other_keys(newer):
    result = smt._schema_inclusion(JSON_TEXT, newer)
    assert result.verdict == "falsified", str(result)
    assert smt._admits(adapt_row(JSON_TEXT), result.witness)
    assert not smt._admits(adapt_row(newer), result.witness)
    assert set(result.witness) - {"s"}, result.witness
