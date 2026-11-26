# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A pattern and a length on the string items of a JSON Schema array are read exactly: the
narrower side is included in the wider, the wider is falsified with a confirmed witness."""
import pytest

pytest.importorskip("z3")
pytest.importorskip("jsonschema")

import jsonschema  # noqa: E402

from mathema_language import smt  # noqa: E402


def _array(items):
    return {"type": "object", "required": ["f"],
            "properties": {"f": {"type": "array", "items": {"type": "string", **items}}}}


def _valid(schema, record):
    return jsonschema.Draft202012Validator(schema).is_valid(record)


NARROW, WIDE = {"pattern": r"^/wt/task-7/.*$"}, {"pattern": r"^/wt/.*$"}


def test_a_narrower_item_pattern_is_proven_inside_a_wider():
    assert smt._schema_inclusion(_array(NARROW), _array(WIDE)).verdict == "proven"


def test_a_wider_item_pattern_is_falsified_with_a_confirmed_witness():
    older, newer = _array(WIDE), _array(NARROW)
    result = smt._schema_inclusion(older, newer)
    assert result.verdict == "falsified", str(result)
    assert _valid(older, result.witness) and not _valid(newer, result.witness)


@pytest.mark.parametrize("older,newer", [({"maxLength": 3}, {"maxLength": 5}),
                                         ({"minLength": 3}, {"minLength": 1})])
def test_item_lengths_widen_proven(older, newer):
    assert smt._schema_inclusion(_array(older), _array(newer)).verdict == "proven"


@pytest.mark.parametrize("older,newer", [({"maxLength": 5}, {"maxLength": 3}),
                                         ({"minLength": 1}, {"minLength": 3}),
                                         ({}, {"pattern": "^a"})])
def test_item_lengths_and_patterns_narrow_falsified_with_a_witness(older, newer):
    result = smt._schema_inclusion(_array(older), _array(newer))
    assert result.verdict == "falsified", str(result)
    assert _valid(_array(older), result.witness) and not _valid(_array(newer), result.witness)
