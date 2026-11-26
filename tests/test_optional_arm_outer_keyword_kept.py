# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A JSON Schema property that spells a bound on both the property and an `anyOf` arm is read
with the arm's bound only; jsonschema enforces both, so the tighter one holds.

On origin/main the outer bound was read and the arm's dropped (the newer-narrower pair was
falsified); with the arm merged over the outer, a narrowing is proven.
"""
import pytest

pytest.importorskip("z3")
pytest.importorskip("jsonschema")

import jsonschema  # noqa: E402

from mathema_language import smt  # noqa: E402

NULL = {"type": "null"}


def _schema(prop):
    return {"type": "object", "required": ["f"], "properties": {"f": prop}}


def _ok(schema, value):
    try:
        jsonschema.validate({"f": value}, schema)
        return True
    except jsonschema.ValidationError:
        return False


@pytest.mark.parametrize("key", ["anyOf", "oneOf"])
def test_outer_max_tighter_than_arm_max_is_not_lost(key):
    older = _schema({"maximum": 5, key: [{"type": "integer", "maximum": 8}, NULL]})
    newer = _schema({"maximum": 3, key: [{"type": "integer", "maximum": 8}, NULL]})
    assert _ok(older, 4) and not _ok(newer, 4)
    assert smt._schema_inclusion(older, newer).verdict != "proven"


def test_outer_min_tighter_than_arm_min_is_not_lost():
    older = _schema({"anyOf": [{"type": "integer", "minimum": 0}, NULL]})
    newer = _schema({"minimum": 3, "anyOf": [{"type": "integer", "minimum": 0}, NULL]})
    assert _ok(older, 0) and not _ok(newer, 0)
    assert smt._schema_inclusion(older, newer).verdict != "proven"


def test_outer_max_length_tighter_than_arm():
    older = _schema({"anyOf": [{"type": "string", "maxLength": 5}, NULL]})
    newer = _schema({"maxLength": 3, "anyOf": [{"type": "string", "maxLength": 5}, NULL]})
    assert _ok(older, "aaaa") and not _ok(newer, "aaaa")
    assert smt._schema_inclusion(older, newer).verdict != "proven"
