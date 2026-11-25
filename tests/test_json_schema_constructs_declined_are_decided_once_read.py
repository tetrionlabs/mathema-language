# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""JSON Schema constructs declined today (a schema for other keys, a required key no property
names), and the verdicts the encoding owes once it reads them: a true inclusion is proven, and a false one is
falsified with a record both sides' validation separates. Each is expected to fail until then."""

import pytest

pytest.importorskip("z3")
jsonschema = pytest.importorskip("jsonschema")

from mathema_language.schema.adaptors import adapt_row  # noqa: E402
from mathema_language.smt import _admits, _schema_inclusion  # noqa: E402

DUE = "declined in 0.4.1; the construct is read and this verdict restored by 2026-12-18"
owed = pytest.mark.xfail(strict=True, reason=DUE)


STRINGS_ELSEWHERE = {"type": "object", "properties": {}, "additionalProperties": {"type": "string"}}
INTS_ELSEWHERE = {"type": "object", "properties": {}, "additionalProperties": {"type": "integer"}}
NEEDS_Z = {"type": "object", "properties": {}, "required": ["z"]}
OPEN = {"type": "object", "properties": {}}


def _json_valid(schema, doc):
    try:
        jsonschema.validate(doc, schema)
        return True
    except jsonschema.ValidationError:
        return False


@owed
@pytest.mark.parametrize("older, newer", [
    (STRINGS_ELSEWHERE, STRINGS_ELSEWHERE), (STRINGS_ELSEWHERE, OPEN),
    (NEEDS_Z, NEEDS_Z), (NEEDS_Z, OPEN),
], ids=["value schema into itself", "value schema into open", "bare required into itself",
        "bare required into open"])
def test_a_true_inclusion_over_the_construct_is_proven(older, newer):
    assert _schema_inclusion(older, newer).verdict == "proven"


@owed
@pytest.mark.parametrize("older, newer", [
    (STRINGS_ELSEWHERE, INTS_ELSEWHERE), (OPEN, INTS_ELSEWHERE), (OPEN, NEEDS_Z),
], ids=["string values into int values", "open into int values", "open into bare required"])
def test_a_false_inclusion_over_the_construct_is_falsified(older, newer):
    result = _schema_inclusion(older, newer)
    assert result.verdict == "falsified"
    assert _admits(adapt_row(older), result.witness)
    assert not _admits(adapt_row(newer), result.witness)
    assert _json_valid(older, result.witness) and not _json_valid(newer, result.witness)
