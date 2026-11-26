# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
# ruff: noqa: UP045, UP007
"""Verdicts that changed from origin/main to the PR for the worse (lost true proofs), and
false proofs present on both (not introduced by the PR; the arm of an anyOf is never searched
for keywords the neutral model does not carry)."""
from typing import Annotated, Optional

import pytest

pytest.importorskip("z3")
pytest.importorskip("pydantic")
pytest.importorskip("jsonschema")

import jsonschema  # noqa: E402
from pydantic import Field, ValidationError, conint, constr, create_model  # noqa: E402

from mathema_language import smt  # noqa: E402


def _model(ann):
    return create_model("M", f=(ann, ...))


# --- lost true proofs (proven on origin/main, unknown on the PR) -------------------------------

@pytest.mark.parametrize("ann", [
    Optional[conint(le=5)],
    Optional[constr(max_length=5)],
    Optional[Annotated[str, Field(pattern="^a+$")]],
], ids=["conint", "constr", "pattern"])
def test_identical_optional_models_stay_proven(ann):
    assert smt._schema_inclusion(_model(ann), _model(ann)).verdict == "proven"


def test_optional_conint_narrowing_stays_falsified():
    older, newer = _model(Optional[conint(le=5)]), _model(Optional[conint(le=3)])
    result = smt._schema_inclusion(older, newer)
    assert result.verdict == "falsified"
    older.model_validate(result.witness)
    with pytest.raises(ValidationError):
        newer.model_validate(result.witness)


# --- false proofs on both origin/main and the PR ----------------------------------------------

NULL = {"type": "null"}


def _schema(prop):
    return {"type": "object", "required": ["f"], "properties": {"f": prop}}


@pytest.mark.parametrize("keyword", [{"not": {"const": 4}}, {"allOf": [{"maximum": 3}]}],
                         ids=["not", "allOf"])
def test_enforced_keyword_inside_an_arm_is_not_proven_away(keyword):
    older = _schema({"anyOf": [{"type": "integer"}, NULL]})
    newer = _schema({"anyOf": [{"type": "integer", **keyword}, NULL]})
    value = 4
    jsonschema.validate({"f": value}, older)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"f": value}, newer)
    assert smt._schema_inclusion(older, newer).verdict != "proven"


def test_strict_field_is_not_a_superset_of_lax():
    older = _model(Annotated[int, Field()])
    newer = _model(Annotated[int, Field(strict=True)])
    older.model_validate({"f": True})
    with pytest.raises(ValidationError):
        newer.model_validate({"f": True})
    assert smt._schema_inclusion(older, newer).verdict != "proven"
