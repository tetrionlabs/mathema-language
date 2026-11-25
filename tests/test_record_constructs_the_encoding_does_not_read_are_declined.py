# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Record constructs the encoding does not read leave an inclusion unknown, with the construct
named, never proven: each case states the record that the libraries' own validators separate."""

import jsonschema
import pytest

pytest.importorskip("z3")
pydantic = pytest.importorskip("pydantic")

from mathema_language.smt import _schema_inclusion  # noqa: E402


def _json_valid(schema, doc):
    try:
        jsonschema.validate(doc, schema)
        return True
    except jsonschema.ValidationError:
        return False


def _model_valid(model, doc):
    try:
        model.model_validate(doc)
        return True
    except pydantic.ValidationError:
        return False


def _declined(older, newer, named):
    result = _schema_inclusion(older, newer)
    assert result.verdict == "unknown", result
    assert named in result.reason, result.reason


class _InnerIgnore(pydantic.BaseModel):
    x: int


class _InnerForbid(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    x: int


class _OuterIgnore(pydantic.BaseModel):
    a: _InnerIgnore


class _OuterForbid(pydantic.BaseModel):
    a: _InnerForbid


def test_a_nested_model_with_its_own_extra_setting_is_declined():
    doc = {"a": {"x": 1, "y": 2}}
    assert _model_valid(_OuterIgnore, doc) and not _model_valid(_OuterForbid, doc)
    _declined(_OuterIgnore, _OuterForbid, "extra")


@pytest.mark.parametrize("older, newer, doc", [
    ({"type": "object", "properties": {}, "additionalProperties": {"type": "string"}},
     {"type": "object", "properties": {}, "additionalProperties": {"type": "integer"}},
     {"k": "s"}),
    ({"type": "object", "properties": {}},
     {"type": "object", "properties": {}, "additionalProperties": {"type": "integer"}},
     {"k": "s"}),
])
def test_a_schema_on_other_keys_is_declined(older, newer, doc):
    assert _json_valid(older, doc) and not _json_valid(newer, doc)
    _declined(older, newer, "additionalProperties")


def test_a_required_key_with_no_property_is_declined():
    older = {"type": "object", "properties": {}}
    newer = {"type": "object", "properties": {}, "required": ["z"]}
    assert _json_valid(older, {}) and not _json_valid(newer, {})
    _declined(older, newer, "required")


class _LaxInt(pydantic.BaseModel):
    a: int


def test_a_model_that_converts_its_input_is_declined_against_another_library():
    newer = {"type": "object", "properties": {"a": {"type": "integer"}}, "required": ["a"]}
    doc = {"a": "1"}
    assert _model_valid(_LaxInt, doc) and not _json_valid(newer, doc)
    _declined(_LaxInt, newer, "converts")


class _AliasForbid(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    a: str = pydantic.Field(alias="A")


class _PlainForbid(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    a: str


def test_a_field_read_by_an_alias_is_declined():
    doc = {"A": "x"}
    assert _model_valid(_AliasForbid, doc) and not _model_valid(_PlainForbid, doc)
    _declined(_AliasForbid, _PlainForbid, "alias")


class _Text(pydantic.BaseModel):
    s: str


class _StrictInt(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(strict=True)
    a: int


JSON_TEXT = {"type": "object", "required": ["s"], "properties": {"s": {"type": "string"}}}
JSON_INT = {"type": "object", "required": ["a"], "properties": {"a": {"type": "integer"}}}


def test_what_the_encoding_reads_is_still_proven():
    assert _schema_inclusion(_Text, JSON_TEXT).verdict == "proven"
    assert _schema_inclusion(_StrictInt, JSON_INT).verdict == "proven"
    assert _schema_inclusion(_LaxInt, _LaxInt).verdict == "proven"
    assert _schema_inclusion(_PlainForbid, _PlainForbid).verdict == "proven"
    closed = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"],
              "additionalProperties": False}
    assert _schema_inclusion(closed, {**closed, "additionalProperties": {}}).verdict == "proven"
