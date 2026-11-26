# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
# ruff: noqa: UP045, UP007, F401
"""A constraint inside the non-None arm of an optional field is read, not dropped.

`Optional[Annotated[T, Field(...)]]` and `Annotated[T, Field(...)] | None` carry the
constraint on the arm; pydantic applies it, so narrowing it is not an inclusion.
"""
from decimal import Decimal
from typing import Annotated, Optional

import pytest

pytest.importorskip("z3")
pytest.importorskip("pydantic")

from pydantic import BaseModel, Field, ValidationError, create_model  # noqa: E402

from mathema_language.smt import _schema_inclusion  # noqa: E402

CASES = [
    (int, {"le": 5}, {"le": 3}, 4),
    (Decimal, {"le": 5}, {"le": 3}, Decimal(4)),
    (Decimal, {"max_digits": 6, "decimal_places": 2}, {"max_digits": 4, "decimal_places": 2},
     Decimal("100.00")),
    (Decimal, {"max_digits": 6, "decimal_places": 3, "lt": Decimal(-50)},
     {"max_digits": 5, "decimal_places": 3}, Decimal("-100.00")),
]


def _pair(base, older, newer, form):
    def wrap(kw):
        arm = Annotated[base, Field(**kw)]
        return Optional[arm] if form == "optional" else arm | None
    return (create_model("Older", f0=(wrap(older), ...)),
            create_model("Newer", f0=(wrap(newer), ...)))


@pytest.mark.parametrize("form", ["optional", "pipe"])
@pytest.mark.parametrize("base,older,newer,value", CASES)
def test_a_narrowed_arm_is_not_proven(base, older, newer, value, form):
    A, B = _pair(base, older, newer, form)
    A.model_validate({"f0": value})
    with pytest.raises(ValidationError):
        B.model_validate({"f0": value})
    assert _schema_inclusion(A, B).verdict != "proven"
