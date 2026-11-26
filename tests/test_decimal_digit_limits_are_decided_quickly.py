# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Decimal inclusion questions with digit limits are decided, not timed out."""
import time
from decimal import Decimal

import pytest

pytest.importorskip("z3")
pytest.importorskip("pydantic")
pytest.importorskip("jsonschema")

from pydantic import BaseModel, Field  # noqa: E402

from mathema_language.smt import _schema_inclusion  # noqa: E402

LIMIT_SECONDS = 3.0


def _model(digits, places, **extra):
    class M(BaseModel):
        pence: Decimal = Field(max_digits=digits, decimal_places=places, **extra)
    return M


def _timed(a, b):
    start = time.monotonic()
    result = _schema_inclusion(a, b)
    return result, time.monotonic() - start


def _verdict(result):
    return result.verdict


@pytest.mark.parametrize("older,newer,expected", [
    ((6, 2), (8, 2), "proven"),
    ((8, 2), (6, 2), "falsified"),
    ((6, 2), (6, 2), "proven"),
    ((6, 2), (6, 3), "proven"),
    ((6, 3), (6, 2), "falsified"),
    ((6, 2), (5, 2), "falsified"),
])
def test_digit_limits_with_a_lower_bound(older, newer, expected):
    a = _model(*older, ge=0)
    b = _model(*newer, ge=0)
    result, seconds = _timed(a, b)
    assert _verdict(result) == expected, result
    assert seconds < LIMIT_SECONDS


def test_digit_limits_without_bounds():
    result, seconds = _timed(_model(6, 2), _model(8, 2))
    assert _verdict(result) == "proven", result
    assert seconds < LIMIT_SECONDS
    result, seconds = _timed(_model(8, 2), _model(6, 2))
    assert _verdict(result) == "falsified", result
    assert seconds < LIMIT_SECONDS


def test_precision_only_stays_declined():
    class P(BaseModel):
        pence: Decimal = Field(max_digits=6)

    class Q(BaseModel):
        pence: Decimal = Field(max_digits=8)
    assert _verdict(_schema_inclusion(P, Q)) == "unknown"


def test_scale_only_stays_declined():
    class P(BaseModel):
        pence: Decimal = Field(decimal_places=2)

    class Q(BaseModel):
        pence: Decimal = Field(decimal_places=3)
    assert _verdict(_schema_inclusion(P, Q)) == "unknown"
