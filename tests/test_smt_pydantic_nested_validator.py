# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A custom validator on a model nested inside another is not read by the
record encoding, as one on the outer model is not: an inclusion over it
is unknown with the reason."""
import pytest

pytest.importorskip("z3")
pydantic = pytest.importorskip("pydantic")

from pydantic import BaseModel, field_validator  # noqa: E402

from mathema_language import smt  # noqa: E402


class Inner(BaseModel):
    y: int


class Checked(BaseModel):
    y: int

    @field_validator("y")
    @classmethod
    def small(cls, value: int) -> int:
        if value > 3:
            raise ValueError("too big")
        return value


class Outer(BaseModel):
    r: Inner


class OuterChecked(BaseModel):
    r: Checked


def test_a_validator_on_a_nested_model_is_not_read():
    assert Outer(r={"y": 9}) and pytest.raises(pydantic.ValidationError, OuterChecked, r={"y": 9})
    result = smt._schema_inclusion(Outer, OuterChecked)
    assert result.verdict == "unknown", result
    assert "validator" in result.reason
