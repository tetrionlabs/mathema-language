# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A pydantic model compared with a JSON Schema: lax conversion of input is declined, by name,
never proven; what the encoding reads is still proven."""

import pytest

pytest.importorskip("z3")
jsonschema = pytest.importorskip("jsonschema")
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



class _LaxInt(pydantic.BaseModel):
    a: int


def test_a_model_that_converts_its_input_is_declined_against_another_library():
    newer = {"type": "object", "properties": {"a": {"type": "integer"}}, "required": ["a"]}
    doc = {"a": "1"}
    assert _model_valid(_LaxInt, doc) and not _json_valid(newer, doc)
    _declined(_LaxInt, newer, "converts")



class _Text(pydantic.BaseModel):
    s: str


class _StrictInt(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(strict=True)
    a: int


JSON_TEXT = {"type": "object", "required": ["s"], "properties": {"s": {"type": "string"}}}
JSON_INT = {"type": "object", "required": ["a"], "properties": {"a": {"type": "integer"}}}


def test_what_the_encoding_reads_across_the_two_libraries_is_still_proven():
    assert _schema_inclusion(_Text, JSON_TEXT).verdict == "proven"
    assert _schema_inclusion(_StrictInt, JSON_INT).verdict == "proven"
