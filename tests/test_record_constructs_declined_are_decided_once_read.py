# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The verdicts the encoding owes for the record constructs it declines today: a true inclusion
over each construct is proven, and a false one is falsified with a record the libraries' own
validators separate. Each is expected to fail until the construct is read."""

import jsonschema
import pytest

pytest.importorskip("z3")
pydantic = pytest.importorskip("pydantic")

from mathema_language.schema.adaptors import adapt_row  # noqa: E402
from mathema_language.smt import _admits, _schema_inclusion  # noqa: E402

DUE = "declined in 0.4.1; the construct is read and this verdict restored by 2026-12-18"
owed = pytest.mark.xfail(strict=True, reason=DUE)


class _InnerForbid(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    x: int


class _InnerIgnore(pydantic.BaseModel):
    x: int


class _OuterForbid(pydantic.BaseModel):
    a: _InnerForbid


class _OuterIgnore(pydantic.BaseModel):
    a: _InnerIgnore


class _Alias(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    a: str = pydantic.Field(alias="A")


class _PlainForbid(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    a: str


class _LaxInt(pydantic.BaseModel):
    a: int


STRINGS_ELSEWHERE = {"type": "object", "properties": {}, "additionalProperties": {"type": "string"}}
INTS_ELSEWHERE = {"type": "object", "properties": {}, "additionalProperties": {"type": "integer"}}
NEEDS_Z = {"type": "object", "properties": {}, "required": ["z"]}
OPEN = {"type": "object", "properties": {}}
ANY_A = {"type": "object", "properties": {"a": {}}, "required": ["a"]}
INT_A = {"type": "object", "properties": {"a": {"type": "integer"}}, "required": ["a"]}


@owed
@pytest.mark.parametrize("older, newer", [
    (_OuterForbid, _OuterForbid),
    (_OuterForbid, _OuterIgnore),
    (STRINGS_ELSEWHERE, STRINGS_ELSEWHERE),
    (STRINGS_ELSEWHERE, OPEN),
    (NEEDS_Z, NEEDS_Z),
    (NEEDS_Z, OPEN),
    (_LaxInt, ANY_A),
    (_Alias, _Alias),
], ids=["nested forbid into itself", "nested forbid into nested ignore",
        "value schema into itself", "value schema into open", "bare required into itself",
        "bare required into open", "lax int into any value", "alias into itself"])
def test_a_true_inclusion_over_the_construct_is_proven(older, newer):
    assert _schema_inclusion(older, newer).verdict == "proven"


@owed
@pytest.mark.parametrize("older, newer", [
    (_OuterIgnore, _OuterForbid),
    (STRINGS_ELSEWHERE, INTS_ELSEWHERE),
    (OPEN, INTS_ELSEWHERE),
    (OPEN, NEEDS_Z),
    (_LaxInt, INT_A),
    (_Alias, _PlainForbid),
], ids=["nested ignore into nested forbid", "string values into int values",
        "open into int values", "open into bare required", "lax int into int schema",
        "alias into field name"])
def test_a_false_inclusion_over_the_construct_is_falsified(older, newer):
    result = _schema_inclusion(older, newer)
    assert result.verdict == "falsified"
    assert _admits(adapt_row(older), result.witness)
    assert not _admits(adapt_row(newer), result.witness)
    # the validators themselves, where they take a plain document
    for side, admitted in ((older, True), (newer, False)):
        if isinstance(side, dict):
            try:
                jsonschema.validate(result.witness, side)
                ok = True
            except jsonschema.ValidationError:
                ok = False
            assert ok is admitted
