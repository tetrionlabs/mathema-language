# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A field's name means one field whatever the encoding has read: an
inclusion read older first or newer first gives one answer, the
float-bound check reads a field of the top record named with a dot as
that field and not as a nested one, and reading a record never changes
the values it is built from."""
import copy
import itertools
import random

import pytest

z3 = pytest.importorskip("z3")
jsonschema = pytest.importorskip("jsonschema")

from mathema_language import smt  # noqa: E402
from mathema_language.schema.adaptors import adapt_row  # noqa: E402

INNER = {"type": "object", "properties": {"b": {"enum": [1]}}, "required": ["b"]}


def closed(props, required=None):
    return {"type": "object", "properties": props, "additionalProperties": False,
            "required": list(props) if required is None else required}


def valid(schema, value):
    return jsonschema.Draft202012Validator(schema).is_valid(value)


def both_orders(older, newer):
    lo, ln = adapt_row(older), adapt_row(newer)
    names = list(dict.fromkeys([*smt.field_names(lo), *smt.field_names(ln)]))
    out = []
    for first in ("older", "newer"):
        enc = smt.new_encoding()
        if first == "older":
            mo, mn = enc.language(lo, names, "older"), enc.language(ln, names, "newer")
        else:
            mn = enc.language(ln, names, "newer")
            mo = enc.language(lo, names, "older")
        solver = z3.Solver()
        solver.add(mo, z3.Not(mn))
        out.append(solver.check())
    return out


def test_a_closed_record_refuses_a_dotted_top_field_in_either_order():
    older = closed({"a.b": {"enum": [1]}, "a": INNER})
    newer = closed({"a": INNER})
    assert valid(older, {"a.b": 1, "a": {"b": 1}}) and not valid(newer, {"a.b": 1, "a": {"b": 1}})
    assert both_orders(older, newer) == [z3.sat, z3.sat]


def test_rows_read_in_either_order_agree():
    lo, ln = adapt_row(closed({"a.b": {"enum": [1]}, "a": INNER})), adapt_row(closed({"a": INNER}))
    own = smt.field_names(lo)
    answers = []
    for first in ("old", "new"):
        enc = smt.new_encoding()
        if first == "old":
            inside = enc.row(lo.schema, own, "older", True)
            still = enc.row(ln.schema, own, "newer", True)
        else:
            still = enc.row(ln.schema, own, "newer", True)
            inside = enc.row(lo.schema, own, "older", True)
        solver = z3.Solver()
        solver.add(inside, z3.Not(still))
        answers.append(solver.check())
    assert answers == [z3.sat, z3.sat]


@pytest.mark.parametrize("name", ["a.b", "ab", "a\\b", "a\\.b"])
def test_a_float_bound_on_a_dotted_top_field_is_not_read_as_a_nested_field(name):
    inner = {"type": "object", "properties": {"b": {"enum": [5]}}, "required": ["b"]}
    older = {"type": "object", "properties": {name: {"type": "number", "maximum": 1.0},
                                              "a": inner}, "required": [name, "a"]}
    newer = {"type": "object", "properties": {"a": inner}, "required": ["a"]}
    result = smt._schema_inclusion(older, newer)
    assert result.verdict == "proven", result


def test_reading_a_record_leaves_the_values_it_is_built_from_as_they_were():
    language = adapt_row(closed({"a": closed({"b": {"enum": [1]}}), "a\\.b": {"enum": [2]}}))
    values = {"a": {"x": 0}, "a.b": 1}
    kept = copy.deepcopy(values)
    smt._nest(language, values)
    smt._admits(language, values)
    smt.build(language, values)
    assert values == kept


NAMES = ["a", "b", "a.b", "a\\", "a\\.b", "b.a", "\x00", ""]


def _shape(rng):
    props = {}
    for name in rng.sample(NAMES, rng.randint(1, 2)):
        if rng.random() < 0.5:
            bound = rng.choice(["maximum", "exclusiveMaximum", "minimum", "exclusiveMinimum"])
            props[name] = {"type": "number", bound: rng.choice([0.0, 1.0])}
        else:
            props[name] = {"enum": rng.sample([1, 2], rng.randint(1, 2))}
    holder = rng.choice(NAMES)
    inner_name = rng.choice(NAMES)
    props[holder] = {"type": "object", "required": [inner_name],
                     "properties": {inner_name: {"enum": rng.sample([1, 2], rng.randint(1, 2))}}}
    return closed(props) if rng.random() < 0.6 else {"type": "object", "properties": props,
                                                     "required": list(props)}


def _records(older, newer):
    names = sorted(set(older["properties"]) | set(newer["properties"]))
    choices = []
    for name in names:
        options: list = [None, 1, 2, 0.0, 1.0, -1.0, 2.5, float.fromhex("0x1.0000000000001p+0"),
                         float.fromhex("0x1.fffffffffffffp-1")]
        for side in (older, newer):
            spec = side["properties"].get(name)
            if spec and spec.get("type") == "object":
                inner = sorted(spec["properties"])
                options += [dict(zip(inner, values, strict=True))
                            for values in itertools.product((1, 2), repeat=len(inner))]
        choices.append(options)
    for values in itertools.product(*choices):
        yield {n: v for n, v in zip(names, values, strict=True) if v is not None}


def test_no_fuzzed_inclusion_with_numbers_is_wrong_in_either_direction_or_order():
    rng = random.Random(20261122)
    decided = 0
    for _ in range(80):
        older, newer = _shape(rng), _shape(rng)
        if rng.random() < 0.4:
            newer = copy.deepcopy(older)
        result = smt._schema_inclusion(older, newer)
        refuting = next((r for r in _records(older, newer)
                         if valid(older, r) and not valid(newer, r)), None)
        if result.verdict == "proven":
            decided += 1
            assert refuting is None, (older, newer, refuting)
        elif result.verdict == "falsified":
            decided += 1
            assert valid(older, result.witness) and not valid(newer, result.witness), \
                (older, newer, result.witness)
        orders = both_orders(older, newer)
        assert orders[0] == orders[1], (older, newer, orders)
    assert decided >= 40, decided
