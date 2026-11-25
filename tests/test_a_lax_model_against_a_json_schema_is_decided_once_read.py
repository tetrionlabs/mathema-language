# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A lax pydantic model compared with a JSON Schema, declined today, and the verdicts the encoding owes once it reads them: a true inclusion is proven, and a false one is
falsified with a record both sides' validation separates. Each is expected to fail until then."""

import pytest

pytest.importorskip("z3")
jsonschema = pytest.importorskip("jsonschema")
pydantic = pytest.importorskip("pydantic")

from mathema_language.schema.adaptors import adapt_row  # noqa: E402
from mathema_language.smt import _admits, _schema_inclusion  # noqa: E402

DUE = "declined in 0.4.1; the construct is read and this verdict restored by 2026-12-18"
owed = pytest.mark.xfail(strict=True, reason=DUE)


class _LaxInt(pydantic.BaseModel):
    a: int


ANY_A = {"type": "object", "properties": {"a": {}}, "required": ["a"]}
INT_A = {"type": "object", "properties": {"a": {"type": "integer"}}, "required": ["a"]}


def _json_valid(schema, doc):
    try:
        jsonschema.validate(doc, schema)
        return True
    except jsonschema.ValidationError:
        return False


@owed
def test_a_lax_int_model_into_any_value_is_proven():
    assert _schema_inclusion(_LaxInt, ANY_A).verdict == "proven"


@owed
def test_a_lax_int_model_into_a_schema_of_ints_is_falsified():
    older, newer = _LaxInt, INT_A
    result = _schema_inclusion(older, newer)
    assert result.verdict == "falsified"
    assert _admits(adapt_row(older), result.witness)
    assert not _admits(adapt_row(newer), result.witness)
    older.model_validate(result.witness)
    assert not _json_valid(newer, result.witness)
