# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A pydantic model that ignores keys it does not declare is not included in one that forbids
them; the reverse inclusion holds."""

import pytest

pytest.importorskip("z3")
pydantic = pytest.importorskip("pydantic")

from mathema_language.smt import _schema_inclusion  # noqa: E402


class _Ignore(pydantic.BaseModel):
    a: str


class _Forbid(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    a: str


def test_pydantic_ignore_into_forbid_is_falsified():
    result = _schema_inclusion(_Ignore, _Forbid)
    assert result.verdict == "falsified", result
    _Ignore.model_validate(result.witness)
    with pytest.raises(pydantic.ValidationError):
        _Forbid.model_validate(result.witness)


def test_pydantic_forbid_into_ignore_is_proven():
    assert _schema_inclusion(_Forbid, _Ignore).verdict == "proven"
