# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A witness the float-bound check finds is a record nested as the
language reads it, so the older schema accepts it and the newer refuses
it, whatever the field's name holds."""
import pytest

pytest.importorskip("z3")
jsonschema = pytest.importorskip("jsonschema")

from mathema_language import smt  # noqa: E402


def valid(schema, value):
    return jsonschema.Draft202012Validator(schema).is_valid(value)


@pytest.mark.parametrize("name", ["x", "x.y", "a\\b", "a\\.b", ""])
def test_a_witness_found_at_a_float_bound_is_accepted_by_older_and_refused_by_newer(
        name, monkeypatch):
    real = smt.MembershipEncoding.language

    def the_solver_finds_nothing(self, language, names, side):
        formula = real(self, language, names, side)
        return self.z3.BoolVal(False) if side == "older" else formula
    monkeypatch.setattr(smt.MembershipEncoding, "language", the_solver_finds_nothing)
    older = {"type": "object", "properties": {name: {"type": "number", "maximum": 1.0}},
             "required": [name]}
    newer = {"type": "object", "properties": {name: {"type": "number", "exclusiveMaximum": 1.0}},
             "required": [name]}
    result = smt._schema_inclusion(older, newer)
    assert result.verdict == "falsified", result
    assert result.witness == {name: 1.0}
    assert valid(older, result.witness) and not valid(newer, result.witness)
