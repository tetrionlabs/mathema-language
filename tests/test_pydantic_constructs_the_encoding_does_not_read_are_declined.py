# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""pydantic constructs the encoding does not read leave an inclusion unknown, with the
construct named, never proven: each case states the record that the libraries' own validators separate."""

import pytest

pytest.importorskip("z3")
pydantic = pytest.importorskip("pydantic")

from mathema_language.smt import _schema_inclusion  # noqa: E402


def _model_valid(model, doc):
    try:
        model.model_validate(doc)
        return True
    except pydantic.ValidationError:
        return False




def _declined(older, newer, named):
    result = _schema_inclusion(older, newer)
    assert result.verdict == "unknown", result
    assert named in result.reason, result.reason



class _InnerIgnore(pydantic.BaseModel):
    x: int


class _InnerForbid(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    x: int


class _OuterIgnore(pydantic.BaseModel):
    a: _InnerIgnore


class _OuterForbid(pydantic.BaseModel):
    a: _InnerForbid


def test_a_nested_model_with_its_own_extra_setting_is_declined():
    doc = {"a": {"x": 1, "y": 2}}
    assert _model_valid(_OuterIgnore, doc) and not _model_valid(_OuterForbid, doc)
    _declined(_OuterIgnore, _OuterForbid, "extra")



class _LaxInt(pydantic.BaseModel):
    a: int


class _AliasForbid(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    a: str = pydantic.Field(alias="A")


class _PlainForbid(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    a: str


def test_a_field_read_by_an_alias_is_declined():
    doc = {"A": "x"}
    assert _model_valid(_AliasForbid, doc) and not _model_valid(_PlainForbid, doc)
    _declined(_AliasForbid, _PlainForbid, "alias")



def test_what_the_encoding_reads_of_a_model_is_still_proven():
    assert _schema_inclusion(_LaxInt, _LaxInt).verdict == "proven"
    assert _schema_inclusion(_PlainForbid, _PlainForbid).verdict == "proven"
