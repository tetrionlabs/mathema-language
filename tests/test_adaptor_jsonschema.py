# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The JSON Schema adaptor passes the conformance checks, returns None
for a dict that is not an object schema, validates with the jsonschema
package, whose `absolute_path` becomes the explanation path, and
refuses a schema when jsonschema is not installed."""
import importlib.util

import pytest

from mathema_language.conformance import foreign_object_problems
from mathema_language.schema.adaptors.jsonschema import adapt
from tests._jsonschema_shapes import ORDER_SCHEMA

NESTED = {"title": "Shipment", "type": "object", "required": ["ship"],
          "properties": {"ship": {"type": "object", "required": ["city"],
                                  "properties": {"city": {"type": "string", "minLength": 1}}}}}


def test_returns_none_for_other_objects():
    assert foreign_object_problems(adapt) == []


def test_without_jsonschema_a_schema_is_refused_with_the_extra(monkeypatch):
    monkeypatch.setattr(importlib.util, "find_spec",
                        lambda name, *a: None if name == "jsonschema" else object())
    with pytest.raises(ImportError, match=r"mathema-language\[jsonschema\]"):
        adapt(ORDER_SCHEMA)


def test_passes_the_conformance_checks():
    pytest.importorskip("jsonschema")
    from mathema_language.conformance import record_adaptor_problems
    assert record_adaptor_problems(ORDER_SCHEMA, adapt=adapt) == []
    language = adapt(ORDER_SCHEMA)
    assert type(language.ecosystem).__name__ == "JsonSchemaEcosystem"


def test_the_absolute_path_is_the_explanation_path():
    jsonschema = pytest.importorskip("jsonschema")
    language = adapt(NESTED)
    problems = language.explain({"ship": {"city": ""}})
    (error,) = jsonschema.validators.validator_for(NESTED)(NESTED).iter_errors({"ship": {"city": ""}})
    assert list(error.absolute_path) == ["ship", "city"]
    assert [(p.path, p.predicate) for p in problems] == [(".ship.city", error.message)]


def _lift_verdict(fn, law):
    from mathema.conjecture import check_conjectures, claim
    (p,) = check_conjectures(fn, [claim(law)])
    assert "UNCORROBORATED" not in (p.note or ""), p.note
    return p.verdict


def total(row) -> float:
    """Quantity times price."""
    return row["qty"] * row["price"]


def width(row) -> int:
    """The columns the sku takes, with a space either side."""
    return len(row["sku"]) + 2


def test_the_lift_reads_the_fields_through_this_adaptor():
    pytest.importorskip("jsonschema")
    assert _lift_verdict(total, "for row in L[tests._jsonschema_shapes.ORDER_SCHEMA], f(row) >= 0") == "proven"
    assert _lift_verdict(width, "for row in L[tests._jsonschema_shapes.ORDER_SCHEMA], f(row) <= 10") == "proven"
    assert _lift_verdict(width, "for row in L[tests._jsonschema_shapes.ORDER_SCHEMA], f(row) <= 9") == "falsified"
