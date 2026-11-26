# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
# ruff: noqa: UP045, UP007
"""Inclusions the encoding proves that the library's own validation contradicts, each with the
value the older side admits and the newer refuses."""
from typing import Annotated, Optional

import pytest

pytest.importorskip("z3")
pytest.importorskip("pydantic")
pytest.importorskip("jsonschema")

import jsonschema  # noqa: E402
from annotated_types import Ge, MinLen  # noqa: E402
from pydantic import Field, ValidationError, create_model  # noqa: E402

from mathema_language import smt  # noqa: E402

NULL = {"type": "null"}
INT = {"type": "integer"}


def _obj(p):
    return {"type": "object", "required": ["x"], "properties": {"x": p}}


def _admits(schema, value):
    return jsonschema.Draft202012Validator(schema).is_valid({"x": value})


JSON_CASES = {
    "outer type excludes null": (
        {"anyOf": [INT, NULL]}, {"type": "integer", "anyOf": [INT, NULL]}, None),
    "outer type excludes null, oneOf": (
        {"anyOf": [{"type": "integer", "maximum": 1}, NULL]},
        {"type": "integer", "oneOf": [NULL, {"type": "integer", "exclusiveMaximum": 3}]}, None),
    "outer const excludes null": (
        {"anyOf": [{"type": "integer", "const": 3}, NULL]}, {"const": 3, "anyOf": [INT, NULL]}, None),
    "oneOf arm that admits null too": (
        {"anyOf": [INT, NULL]}, {"oneOf": [{"type": ["integer", "null"]}, NULL]}, None),
    "anyOf and oneOf on one property": (
        {"anyOf": [INT, NULL]},
        {"anyOf": [INT, NULL], "oneOf": [{"type": "integer", "minimum": 5}, NULL]}, 0),
    "keywords on the null arm": (
        {"anyOf": [INT, NULL]}, {"anyOf": [INT, {"type": "null", "not": {}}]}, None),
    "minItems beside an arm minLength": (
        {"anyOf": [{"type": "array", "items": INT}, NULL]},
        {"minItems": 3, "anyOf": [{"type": "array", "items": INT, "minLength": 0}, NULL]}, [1]),
    "outer minLength on an array arm": (
        {"minLength": 3, "anyOf": [{"type": "array", "items": INT, "minItems": 1}, NULL]},
        {"anyOf": [{"type": "array", "items": INT, "minItems": 3}, NULL]}, [1]),
    "minLength on a plain array": (
        {"type": "array", "items": INT, "minLength": 3},
        {"type": "array", "items": INT, "minItems": 3}, [1]),
}


@pytest.mark.parametrize("name", list(JSON_CASES))
def test_jsonschema_inclusion_is_not_proven_when_the_validator_refutes_it(name):
    old, new, value = JSON_CASES[name]
    older, newer = _obj(old), _obj(new)
    assert _admits(older, value) and not _admits(newer, value)
    assert smt._schema_inclusion(older, newer).verdict != "proven"


def _pyd_admits(model, value):
    try:
        model.model_validate({"x": value})
        return True
    except ValidationError:
        return False


PYD_CASES = {
    # pydantic applies a field-level bound over the one inside the optional arm
    "field ge over arm Ge, right side": (
        Optional[Annotated[int, Ge(3)]], Annotated[Optional[Annotated[int, Ge(3)]], Field(ge=5)], 3),
    "field ge over arm Ge, left side": (
        Annotated[Optional[Annotated[int, Ge(5)]], Field(ge=3)], Optional[Annotated[int, Ge(4)]], 3),
    "field min_length over arm MinLen": (
        Annotated[Optional[Annotated[str, MinLen(5)]], Field(min_length=1, max_length=3)],
        Annotated[Optional[str], Field(min_length=3)], "a"),
}


@pytest.mark.parametrize("name", list(PYD_CASES))
def test_pydantic_inclusion_is_not_proven_when_the_model_refutes_it(name):
    old, new, value = PYD_CASES[name]
    older, newer = create_model("A", x=(old, ...)), create_model("B", x=(new, ...))
    assert _pyd_admits(older, value) and not _pyd_admits(newer, value)
    assert smt._schema_inclusion(older, newer).verdict != "proven"
