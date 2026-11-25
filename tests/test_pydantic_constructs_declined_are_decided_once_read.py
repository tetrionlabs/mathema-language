# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""pydantic constructs declined today (a nested model's own extra setting, a field read by an
alias), and the verdicts the encoding owes once it reads them: a true inclusion is proven, and a false one is
falsified with a record both sides' validation separates. Each is expected to fail until then."""

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


@owed
@pytest.mark.parametrize("older, newer", [
    (_OuterForbid, _OuterForbid), (_OuterForbid, _OuterIgnore), (_Alias, _Alias),
], ids=["nested forbid into itself", "nested forbid into nested ignore", "alias into itself"])
def test_a_true_inclusion_over_the_construct_is_proven(older, newer):
    assert _schema_inclusion(older, newer).verdict == "proven"


@owed
@pytest.mark.parametrize("older, newer", [
    (_OuterIgnore, _OuterForbid), (_Alias, _PlainForbid),
], ids=["nested ignore into nested forbid", "alias into field name"])
def test_a_false_inclusion_over_the_construct_is_falsified(older, newer):
    result = _schema_inclusion(older, newer)
    assert result.verdict == "falsified"
    assert _admits(adapt_row(older), result.witness)
    assert not _admits(adapt_row(newer), result.witness)
    older.model_validate(result.witness)
    with pytest.raises(pydantic.ValidationError):
        newer.model_validate(result.witness)
