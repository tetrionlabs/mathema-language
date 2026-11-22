# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Pydantic decimal settings the record encoding does not read the way
pydantic validates are declined by name wherever they stand: a decimal
with one of its two digit limits in a nested model, and a decimal that
admits NaN and the infinities. A decimal whose digits are all places is
read as pydantic validates it
(tests/test_smt_pydantic_decimal_regressions.py). An inclusion over any
of them is unknown with the reason, never proven on a reading pydantic
does not share."""
import decimal

import pytest

pytest.importorskip("z3")
pydantic = pytest.importorskip("pydantic")

from pydantic import BaseModel, Field  # noqa: E402

from mathema_language import smt  # noqa: E402


class Inner(BaseModel):
    y: decimal.Decimal


class InnerThree(BaseModel):
    y: decimal.Decimal = Field(max_digits=3)


class Outer(BaseModel):
    r: Inner


class OuterThree(BaseModel):
    r: InnerThree


class OuterMaybeThree(BaseModel):
    r: "InnerThree | None" = None


class Zero(BaseModel):
    x: decimal.Decimal = Field(ge=0, le=0)


class AllPlaces(BaseModel):
    x: decimal.Decimal = Field(max_digits=2, decimal_places=2)


class WithSpecials(BaseModel):
    x: decimal.Decimal = Field(allow_inf_nan=True)


class Plain(BaseModel):
    x: decimal.Decimal


def admits(model, value) -> bool:
    try:
        model(**value)
        return True
    except pydantic.ValidationError:
        return False


@pytest.mark.parametrize("older, newer, refuting", [
    (Outer, OuterThree, {"r": {"y": decimal.Decimal("1234")}}),
    (Outer, OuterMaybeThree, {"r": {"y": decimal.Decimal("1234")}}),
    (WithSpecials, Plain, {"x": decimal.Decimal("NaN")}),
])
def test_a_decimal_setting_pydantic_reads_otherwise_is_declined(older, newer, refuting):
    assert admits(older, refuting) and not admits(newer, refuting)
    result = smt._schema_inclusion(older, newer)
    assert result.verdict == "unknown", result
    assert "not translated" in result.reason


def test_a_nested_decimal_with_both_limits_is_still_read():
    class InnerBoth(BaseModel):
        y: decimal.Decimal = Field(max_digits=3, decimal_places=1)

    class OuterBoth(BaseModel):
        r: InnerBoth
    result = smt._schema_inclusion(Outer, OuterBoth)
    assert result.verdict == "falsified", result
    assert admits(Outer, result.witness) and not admits(OuterBoth, result.witness)
