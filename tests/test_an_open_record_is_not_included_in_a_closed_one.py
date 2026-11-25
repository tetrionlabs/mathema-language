# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""An open record admits keys it does not declare, so a closed record that
declares the same fields does not include it; the reverse inclusion holds."""

import pytest

pytest.importorskip("z3")
jsonschema = pytest.importorskip("jsonschema")
pydantic = pytest.importorskip("pydantic")

from mathema_language.smt import _schema_inclusion  # noqa: E402

OPEN = {"type": "object", "properties": {"a": {"type": "string"}}}
CLOSED = {**OPEN, "additionalProperties": False}


def _valid(schema, doc):
    try:
        jsonschema.validate(doc, schema)
        return True
    except jsonschema.ValidationError:
        return False


def test_open_root_into_closed_root_is_falsified_with_a_confirmed_key():
    result = _schema_inclusion(OPEN, CLOSED)
    assert result.verdict == "falsified", result
    assert _valid(OPEN, result.witness) and not _valid(CLOSED, result.witness)


def test_open_root_with_required_field_into_closed_root_is_falsified():
    older = {**OPEN, "required": ["a"]}
    newer = {**older, "additionalProperties": False}
    result = _schema_inclusion(older, newer)
    assert result.verdict == "falsified", result
    assert _valid(older, result.witness) and not _valid(newer, result.witness)


def test_closed_root_into_open_root_is_proven():
    assert _schema_inclusion(CLOSED, OPEN).verdict == "proven"


def test_open_into_open_and_closed_into_closed_stay_proven():
    assert _schema_inclusion(OPEN, OPEN).verdict == "proven"
    assert _schema_inclusion(CLOSED, CLOSED).verdict == "proven"


def test_closed_root_declaring_more_fields_still_excludes_other_keys():
    newer = {"type": "object", "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
             "additionalProperties": False}
    result = _schema_inclusion(OPEN, newer)
    assert result.verdict == "falsified", result
    assert _valid(OPEN, result.witness) and not _valid(newer, result.witness)


def test_nested_open_into_nested_closed_is_never_proven():
    older = {"type": "object", "properties": {"r": OPEN}}
    newer = {"type": "object", "properties": {"r": CLOSED}}
    assert _schema_inclusion(older, newer).verdict != "proven"


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
