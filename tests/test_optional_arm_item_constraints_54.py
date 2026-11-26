# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Keywords inside a JSON Schema array's `items` are enforced by the validator on every item, so
an inclusion between two arrays whose items differ only by such a keyword is not proven; each
case here has a record the older schema admits and the newer refuses under jsonschema."""
import pytest

pytest.importorskip("z3")
pytest.importorskip("jsonschema")

import jsonschema  # noqa: E402

from mathema_language import smt  # noqa: E402

NULL = {"type": "null"}


def _schema(prop):
    return {"type": "object", "required": ["f"], "properties": {"f": prop}}


def _array(items):
    return _schema({"type": "array", "items": items})


def _valid(schema, record):
    try:
        jsonschema.validate(record, schema)
        return True
    except jsonschema.ValidationError:
        return False


CASES = {
    "minimum": (_array({"type": "integer"}), _array({"type": "integer", "minimum": 5}),
                {"f": [0]}),
    "maxLength": (_array({"type": "string"}), _array({"type": "string", "maxLength": 1}),
                  {"f": ["ab"]}),
    "enum": (_array({"type": "integer"}), _array({"type": "integer", "enum": [1]}), {"f": [2]}),
    "const": (_array({"type": "integer"}), _array({"type": "integer", "const": 1}), {"f": [2]}),
    "pattern": (_array({"type": "string"}), _array({"type": "string", "pattern": "^a$"}),
                {"f": ["b"]}),
    "multipleOf": (_array({"type": "integer"}), _array({"type": "integer", "multipleOf": 2}),
                   {"f": [1]}),
    "allOf": (_array({"type": "integer"}), _array({"type": "integer", "allOf": [{"minimum": 3}]}),
              {"f": [1]}),
    "not": (_array({"type": "integer"}), _array({"type": "integer", "not": {"const": 1}}),
            {"f": [1]}),
    "nullable items arm": (_array({"type": "integer"}),
                           _array({"anyOf": [{"type": "integer", "minimum": 3}, NULL]}),
                           {"f": [1]}),
    "items inside a nullable arm": (
        _schema({"anyOf": [{"type": "array", "items": {"type": "integer"}}, NULL]}),
        _schema({"anyOf": [{"type": "array", "items": {"type": "integer", "minimum": 3}}, NULL]}),
        {"f": [0]}),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_an_item_keyword_is_never_proven_away(name):
    older, newer, record = CASES[name]
    assert _valid(older, record) and not _valid(newer, record)
    result = smt._schema_inclusion(older, newer)
    assert result.verdict != "proven", str(result)
    if result.verdict == "falsified":
        assert _valid(older, result.witness) and not _valid(newer, result.witness)
