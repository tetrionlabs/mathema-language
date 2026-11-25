# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""JSON Schema constructs the encoding does not read leave an inclusion unknown, with the
construct named, never proven: each case states the record that the libraries' own validators separate."""

import pytest

pytest.importorskip("z3")
jsonschema = pytest.importorskip("jsonschema")

from mathema_language.smt import _schema_inclusion  # noqa: E402


def _json_valid(schema, doc):
    try:
        jsonschema.validate(doc, schema)
        return True
    except jsonschema.ValidationError:
        return False




def _declined(older, newer, named):
    result = _schema_inclusion(older, newer)
    assert result.verdict == "unknown", result
    assert named in result.reason, result.reason



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



def test_a_closed_object_into_any_value_for_other_keys_is_still_proven():
    closed = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"],
              "additionalProperties": False}
    assert _schema_inclusion(closed, {**closed, "additionalProperties": {}}).verdict == "proven"
