# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A decimal field with one of its two digit limits, a precision with no
scale or a scale with no precision, is not read by the record encoding:
an inclusion over it is unknown with the reason, never proven or
falsified on a reading the validation does not share. A decimal with
both limits, or neither, is read as before."""
import decimal

import pytest

pytest.importorskip("z3")

from mathema_language import smt  # noqa: E402
from mathema_language.schema import (  # noqa: E402
    Field,
    NeutralType,
    PlainEcosystem,
    RowLanguage,
    RowSchema,
)


def record(precision, scale, nested=False):
    t = NeutralType("decimal", precision=precision, scale=scale)
    field = Field("x", t)
    if nested:
        field = Field("r", NeutralType("struct", fields=(field,)))
    return RowLanguage(RowSchema("r", (field,)), PlainEcosystem(), "r")


@pytest.mark.parametrize("older, newer", [
    ((3, None), (2, None)), ((5, None), (5, 0)), ((None, 2), (None, 1)), ((3, None), (3, 0)),
])
@pytest.mark.parametrize("nested", [False, True])
def test_a_decimal_with_one_digit_limit_is_unknown_with_the_reason(older, newer, nested):
    result = smt._schema_inclusion(record(*older, nested), record(*newer, nested))
    assert result.verdict == "unknown", result
    assert "decimal" in result.reason and "digit" in result.reason
    assert smt.untranslated(record(*older, nested)) is not None


def test_the_counterexample_the_encoding_missed_is_real():
    older, newer = record(3, None), record(2, None)
    assert older.contains({"x": decimal.Decimal("123")})
    assert not newer.contains({"x": decimal.Decimal("123")})


@pytest.mark.parametrize("older, newer, verdict", [
    ((3, 0), (2, 0), "falsified"), ((5, 2), (5, 1), "falsified"), ((2, 0), (3, 0), "proven"),
    ((None, None), (None, None), "proven"),
])
def test_a_decimal_with_both_limits_or_neither_is_decided(older, newer, verdict):
    result = smt._schema_inclusion(record(*older), record(*newer))
    assert result.verdict == verdict, result
