# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A shape the encoding reads only roughly is named in the result even when the solver's
counterexample is not confirmed by the validations, so the reason points at the shape and not at
a gap in the encoding."""
import pytest

pytest.importorskip("z3")
pytest.importorskip("jsonschema")

from mathema_language import smt  # noqa: E402


def _schema(prop):
    return {"type": "object", "required": ["f"], "properties": {"f": prop}}


def test_an_item_count_on_a_string_is_named_when_the_offered_record_is_not_confirmed():
    older = _schema({"type": "string"})
    newer = _schema({"type": "string", "minItems": 3})
    result = smt._schema_inclusion(older, newer)
    assert result.verdict == "unknown"
    assert "minItems on a string" in str(result), str(result)
