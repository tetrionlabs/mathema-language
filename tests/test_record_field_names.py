# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A field of a record is one variable of the inclusion question whatever
its name holds: a field whose name holds a dot, a bracket, a quote, a
space, a backslash or the NUL character, or is empty, is never the same
variable as a field of a nested record, or as another field."""
import itertools
import random

import pytest

pytest.importorskip("z3")
jsonschema = pytest.importorskip("jsonschema")

from mathema_language import smt  # noqa: E402
from mathema_language.schema.adaptors import adapt_row  # noqa: E402


def closed(props):
    return {"type": "object", "properties": props, "required": list(props),
            "additionalProperties": False}


INNER = {"type": "object", "properties": {"b": {"enum": [2]}}, "required": ["b"]}


def valid(schema, value):
    return jsonschema.Draft202012Validator(schema).is_valid(value)


def test_a_field_named_with_a_dot_is_not_the_field_of_a_nested_record():
    older = closed({"a.b": {"enum": [1]}, "a": INNER})
    newer = closed({"a.b": {"enum": [7]}, "a": INNER})
    assert valid(older, {"a.b": 1, "a": {"b": 2}}) and not valid(newer, {"a.b": 1, "a": {"b": 2}})
    result = smt._schema_inclusion(older, newer)
    assert result.verdict == "falsified", result
    assert valid(older, result.witness) and not valid(newer, result.witness)


@pytest.mark.parametrize("name", ["a.b", "a[0]", "a]", "a\"b", "a'b", "a b", "a\\b", "a\\.b",
                                  "a\x00b", "a\x00", ".", "\\", "a."])
def test_two_fields_whose_names_differ_are_two_variables(name):
    other = "a" if name != "a" else "b"
    older = closed({name: {"enum": [1]}, other: {"enum": [1]}})
    newer = closed({name: {"enum": [1]}, other: {"enum": [2]}})
    result = smt._schema_inclusion(older, newer)
    assert result.verdict == "falsified", result
    assert valid(older, result.witness) and not valid(newer, result.witness)
    assert smt._schema_inclusion(older, older).verdict == "proven"


@pytest.mark.parametrize("outer, inner", [("a", "b.c"), ("a.b", "c"), ("a\x00", "b"),
                                          ("a", "\x00b"), ("a\\", "b"), ("a", "\\b")])
def test_a_nested_field_is_told_from_a_top_field_spelled_like_its_path(outer, inner):
    spelled = f"{outer}.{inner}"
    nested = {"type": "object", "properties": {inner: {"enum": [2]}}, "required": [inner]}
    older = closed({spelled: {"enum": [1]}, outer: nested})
    newer = closed({spelled: {"enum": [1]}, outer: {**nested,
                                                     "properties": {inner: {"enum": [3]}}}})
    result = smt._schema_inclusion(older, newer)
    assert result.verdict == "falsified", result
    assert result.witness[outer] == {inner: 2}
    assert valid(older, result.witness) and not valid(newer, result.witness)


def test_the_names_of_a_language_tell_a_dotted_field_from_a_nested_one():
    language = adapt_row(closed({"a.b": {"enum": [1]}, "a": INNER}))
    names = smt.field_names(language)
    assert len(names) == len(set(names)) == 3
    assert "a" in names and "a.b" in names


NAMES = ["a", "b", "a.b", "a[0]", "]", "\"", "'", " ", "a b", "\x00", "a\x00b", "", "\\",
         "a\\.b", ".", "b.a"]


def _shape(rng):
    props = {}
    for name in rng.sample(NAMES, rng.randint(1, 3)):
        props[name] = {"enum": rng.sample([1, 2, 3], rng.randint(1, 2))}
    holder = rng.choice(NAMES)
    inner_names = rng.sample(NAMES, rng.randint(1, 2))
    inner = {"type": "object", "required": inner_names,
             "properties": {n: {"enum": rng.sample([1, 2, 3], rng.randint(1, 2))}
                            for n in inner_names}}
    if rng.random() < 0.5:
        inner["additionalProperties"] = False
    props[holder] = inner
    return closed(props)


def _records(older, newer):
    names = sorted(set(older["properties"]) | set(newer["properties"]))
    choices = []
    for name in names:
        options = [None, 1, 2, 3]
        for side in (older, newer):
            spec = side["properties"].get(name)
            if spec and spec.get("type") == "object":
                inner = sorted(spec["properties"])
                options += [dict(zip(inner, values, strict=True))
                            for values in itertools.product((1, 2, 3), repeat=len(inner))]
        choices.append(options)
    for values in itertools.product(*choices):
        yield {n: v for n, v in zip(names, values, strict=True) if v is not None}


def test_no_inclusion_between_fuzzed_records_is_proven_when_a_record_refutes_it():
    rng = random.Random(20261121)
    proven = falsified = 0
    for _ in range(120):
        older, newer = _shape(rng), _shape(rng)
        if rng.random() < 0.4:
            newer = {**older, "properties": {**older["properties"]}}
            name = rng.choice(sorted(newer["properties"]))
            if newer["properties"][name].get("enum"):
                newer["properties"][name] = {"enum": [1, 2]}
        result = smt._schema_inclusion(older, newer)
        if result.verdict == "proven":
            proven += 1
            refuting = next((r for r in _records(older, newer)
                             if valid(older, r) and not valid(newer, r)), None)
            assert refuting is None, (older, newer, refuting)
        elif result.verdict == "falsified":
            falsified += 1
            assert valid(older, result.witness) and not valid(newer, result.witness), \
                (older, newer, result.witness)
    assert proven >= 10 and falsified >= 10, (proven, falsified)
