# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
# ruff: noqa: UP045, UP007
"""Bounds on a JSON Schema property and its `anyOf` arm combine to the tighter; other keywords on
both with different values, unread keywords inside an arm and a field-level `strict` are declined
by name; widened twins stay proven."""
from typing import Annotated, Optional

import pytest

pytest.importorskip("z3")
pytest.importorskip("pydantic")
pytest.importorskip("jsonschema")

from pydantic import Field, create_model  # noqa: E402

from mathema_language import smt  # noqa: E402

NULL = {"type": "null"}


def _schema(prop):
    return {"type": "object", "required": ["f"], "properties": {"f": prop}}


def test_a_bound_on_both_the_property_and_the_arm_is_declined_by_name():
    older = _schema({"maximum": 9, "anyOf": [{"type": "integer", "maximum": 3}, NULL]})
    newer = _schema({"anyOf": [{"type": "integer", "maximum": 5}, NULL]})
    result = smt._schema_inclusion(older, newer)
    assert result.verdict == "unknown"
    assert "maximum" in str(result)


def test_a_bound_on_the_property_beside_an_arm_without_it_stays_read():
    older = _schema({"maximum": 3, "anyOf": [{"type": "integer", "minimum": 0}, NULL]})
    newer = _schema({"maximum": 5, "anyOf": [{"type": "integer", "minimum": 0}, NULL]})
    assert smt._schema_inclusion(older, newer).verdict == "proven"
    assert smt._schema_inclusion(newer, older).verdict == "falsified"


def test_a_keyword_on_both_with_different_values_is_declined_by_name():
    older = _schema({"pattern": "^a", "anyOf": [{"type": "string", "pattern": "^b"}, NULL]})
    result = smt._schema_inclusion(older, older)
    assert result.verdict == "unknown"
    assert "pattern" in str(result)


def test_an_unread_keyword_inside_a_oneof_arm_is_named():
    older = _schema({"oneOf": [{"type": "integer"}, NULL]})
    newer = _schema({"oneOf": [{"type": "integer", "not": {"const": 4}}, NULL]})
    result = smt._schema_inclusion(older, newer)
    assert result.verdict == "unknown"
    assert "'not'" in str(result)


def test_field_level_strict_is_named():
    model = create_model("M", f=(Annotated[int, Field(strict=True)], ...))
    result = smt._schema_inclusion(model, model)
    assert result.verdict == "unknown"
    assert "strict" in str(result)


def test_strict_inside_an_optional_arm_is_named():
    model = create_model("M", f=(Optional[Annotated[int, Field(strict=True)]], ...))
    assert smt._schema_inclusion(model, model).verdict == "unknown"


def test_allow_inf_nan_in_an_arm_is_named_as_on_a_plain_field():
    arm = create_model("M", f=(Optional[Annotated[float, Field(allow_inf_nan=True)]], ...))
    plain = create_model("P", f=(Annotated[float, Field(allow_inf_nan=True)], ...))
    assert smt._schema_inclusion(arm, arm).verdict == "unknown"
    assert smt._schema_inclusion(plain, plain).verdict == "unknown"
