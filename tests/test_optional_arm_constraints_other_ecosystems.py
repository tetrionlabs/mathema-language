# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
# ruff: noqa: UP045, UP007, F401
"""A constraint inside the non-None arm of an optional field is read for dataclasses,
TypedDicts and JSON Schema `anyOf`, as for pydantic models; the widened direction stays proven.
"""
from dataclasses import dataclass
from typing import Annotated, Optional, TypedDict

import pytest

pytest.importorskip("z3")
pytest.importorskip("pydantic")
pytest.importorskip("jsonschema")

from annotated_types import Le  # noqa: E402
from pydantic import Field, ValidationError, create_model  # noqa: E402

from mathema_language import smt  # noqa: E402
from mathema_language.schema.adaptors import adapt_row  # noqa: E402


def _dataclass(le):
    @dataclass
    class Rec:
        f0: Optional[Annotated[int, Le(le)]]
    return Rec


def _typeddict(le):
    class Rec(TypedDict):
        f0: Optional[Annotated[int, Le(le)]]
    return Rec


def _pydantic(le):
    return create_model("Rec", f0=(Optional[Annotated[int, Field(le=le)]], ...))


def _pipe_dataclass(le):
    @dataclass
    class Rec:
        f0: Annotated[int, Le(le)] | None
    return Rec


def _jsonschema(le):
    return {"type": "object", "required": ["f0"],
            "properties": {"f0": {"anyOf": [{"type": "integer", "maximum": le},
                                            {"type": "null"}]}}}


def _jsonschema_one_of(le):
    return {"type": "object", "required": ["f0"],
            "properties": {"f0": {"oneOf": [{"type": "null"},
                                            {"type": "integer", "maximum": le}]}}}


BUILDERS = [_dataclass, _typeddict, _pydantic, _pipe_dataclass, _jsonschema, _jsonschema_one_of]


@pytest.mark.parametrize("build", BUILDERS)
def test_a_narrowed_optional_arm_is_falsified_with_a_witness(build):
    result = smt._schema_inclusion(adapt_row(build(5)), adapt_row(build(3)))
    assert result.verdict == "falsified", str(result)
    value = result.witness["f0"]
    assert 3 < value <= 5
    assert smt._admits(adapt_row(build(5)), result.witness)
    assert not smt._admits(adapt_row(build(3)), result.witness)


@pytest.mark.parametrize("build", BUILDERS)
def test_a_widened_or_equal_optional_arm_stays_proven(build):
    assert smt._schema_inclusion(adapt_row(build(3)), adapt_row(build(5))).verdict == "proven"
    assert smt._schema_inclusion(adapt_row(build(3)), adapt_row(build(3))).verdict == "proven"


def test_the_pydantic_witness_is_refused_by_pydantic():
    older, newer = _pydantic(5), _pydantic(3)
    result = smt._schema_inclusion(older, newer)
    older.model_validate(result.witness)
    with pytest.raises(ValidationError):
        newer.model_validate(result.witness)
