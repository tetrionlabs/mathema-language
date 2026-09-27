# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The JSON Schema adaptor: conforms by the harness, answers not mine
for a dict that is not an object schema, validates with the jsonschema
package, whose `absolute_path` becomes the explanation path, and
refuses a schema when jsonschema is not installed."""
import importlib.util

import pytest

from mathema_language.conformance import not_mine_problems
from mathema_language.schema.adaptors.jsonschema import adapt
from tests._jsonschema_shapes import ORDER_SCHEMA

NESTED = {"title": "Shipment", "type": "object", "required": ["ship"],
          "properties": {"ship": {"type": "object", "required": ["city"],
                                  "properties": {"city": {"type": "string", "minLength": 1}}}}}


def test_not_mine():
    assert not_mine_problems(adapt) == []


def test_without_jsonschema_a_schema_is_refused_with_the_extra(monkeypatch):
    monkeypatch.setattr(importlib.util, "find_spec",
                        lambda name, *a: None if name == "jsonschema" else object())
    with pytest.raises(ImportError, match=r"mathema-language\[jsonschema\]"):
        adapt(ORDER_SCHEMA)


def test_conforms():
    pytest.importorskip("jsonschema")
    from mathema_language.conformance import assert_row_adaptor
    language = assert_row_adaptor(ORDER_SCHEMA, adapt=adapt)
    assert type(language.ecosystem).__name__ == "JsonSchemaEcosystem"


def test_the_absolute_path_is_the_explanation_path():
    jsonschema = pytest.importorskip("jsonschema")
    language = adapt(NESTED)
    problems = language.explain({"ship": {"city": ""}})
    (error,) = jsonschema.validators.validator_for(NESTED)(NESTED).iter_errors({"ship": {"city": ""}})
    assert list(error.absolute_path) == ["ship", "city"]
    assert [(p.path, p.predicate) for p in problems] == [(".ship.city", error.message)]
