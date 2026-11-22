# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Verdicts the record encoding gave rightly before its pydantic decimal
fixes, kept: a decimal whose digits are all places is read as pydantic
validates it (every number the digit rule admits, zero only when written
with a point, as `0.0` and not as `0`), and `allow_inf_nan=False` is no
constraint on a decimal and the one pydantic states on a float."""
import decimal

import pytest

pytest.importorskip("z3")
pydantic = pytest.importorskip("pydantic")

from pydantic import BaseModel, Field  # noqa: E402

from mathema_language import smt  # noqa: E402


class F0(BaseModel):
    x: float


class F1(BaseModel):
    x: float = Field(allow_inf_nan=False)


class D0(BaseModel):
    x: decimal.Decimal


class D1(BaseModel):
    x: decimal.Decimal = Field(allow_inf_nan=False)


class P22(BaseModel):
    x: decimal.Decimal = Field(max_digits=2, decimal_places=2)


class P32(BaseModel):
    x: decimal.Decimal = Field(max_digits=3, decimal_places=2)


class Zero(BaseModel):
    x: decimal.Decimal = Field(ge=0, le=0)


def admits(model, value) -> bool:
    try:
        model(**value)
        return True
    except pydantic.ValidationError:
        return False


@pytest.mark.parametrize("older, newer, verdict", [
    (F0, F1, "falsified"), (D1, D0, "proven"), (D0, D1, "proven"),
    (P22, P22, "proven"), (P22, P32, "proven"), (P32, P22, "falsified"),
    (Zero, P22, "falsified"),
])
def test_a_verdict_given_rightly_before_is_kept(older, newer, verdict):
    result = smt._schema_inclusion(older, newer)
    assert result.verdict == verdict, result
    if verdict == "falsified":
        assert admits(older, result.witness) and not admits(newer, result.witness)


def test_zero_written_without_a_point_is_the_witness_against_an_all_places_field():
    result = smt._schema_inclusion(Zero, P22)
    assert result.witness == {"x": decimal.Decimal("0")}
    assert str(result.witness["x"]) == "0"
