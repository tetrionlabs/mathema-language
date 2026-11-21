# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The encoding names a field one way, whatever has been read before: by
its names from the top record down, each with its backslashes and dots
preceded by a backslash, joined by dots (`field_names`). A plain name
(`x`, `x.qty`) is named as it always was. Every public call reads that
name, and every reader of a record keyed by field name (the float-bound
check, a sampled member, `build`) reads the same one. A solver's text
form of an encoding reads back. A witness is nested by the shape that
admits it. Reading two languages in either order gives one answer."""
import pytest

z3 = pytest.importorskip("z3")
jsonschema = pytest.importorskip("jsonschema")

from mathema_language import smt  # noqa: E402
from mathema_language.schema.adaptors import adapt_row  # noqa: E402
from mathema_language.schema.model import NO_DEFAULT  # noqa: E402
from mathema_language.schema.union import UnionLanguage  # noqa: E402

NAMES = ["ab", "a.b", "a\\b", "x\\", "a\\.b", "é", "a b", "a\x00b", ""]


def closed(props, required=None):
    return {"type": "object", "properties": props, "additionalProperties": False,
            "required": list(props) if required is None else required}


def valid(schema, value):
    return jsonschema.Draft202012Validator(schema).is_valid(value)


@pytest.mark.parametrize("name", NAMES)
def test_a_caller_naming_an_added_field_by_its_field_name_constrains_that_field(name):
    old = adapt_row(closed({"x": {"enum": [1]}}))
    new = adapt_row(closed({"x": {"enum": [1]}, name: {"enum": [5], "default": 5}}, ["x"]))
    enc = smt.MembershipEncoding(z3)
    spelled = dict(zip([f.name for f in new.schema.fields], smt.field_names(new), strict=True))
    own = [spelled[f.name] for f in old.schema.fields]
    added = [f for f in new.schema.fields if spelled[f.name] not in own]
    inside = enc.row(old.schema, own, "older", True)
    still = enc.row(new.schema, own + [spelled[f.name] for f in added], "newer", True)
    carried = [enc.var(spelled[f.name]) == enc.const(f.default) for f in added
               if f.default is not NO_DEFAULT]
    solver = z3.Solver()
    solver.add(*carried, inside, z3.Not(still))
    assert solver.check() == z3.unsat
    assert len(enc.vars) == 2


@pytest.mark.parametrize("name", ["ab", "é", "a b", "a\x00b", ""])
def test_a_plain_name_is_the_field_name_of_that_field(name):
    language = adapt_row(closed({name: {"enum": [1]}}))
    assert smt.field_names(language) == [name]


def test_a_dotted_name_names_a_nested_field():
    language = adapt_row(closed({"x": closed({"qty": {"enum": [1]}})}))
    enc = smt.MembershipEncoding(z3)
    formula = enc.language(language, smt.field_names(language), "older")
    is_number, value = enc.number("x.qty")
    solver = z3.Solver()
    solver.add(formula, is_number, value != 1)
    assert solver.check() == z3.unsat
    assert smt.field_names(language) == ["x", "x.qty"]


def test_field_names_name_each_field_once_and_read_back_to_it():
    language = adapt_row(closed({"a.b": {"enum": [1]}, "a": closed({"b": {"enum": [2]}}),
                                 "c": closed({"d.e": {"enum": [3]}})}))
    names = smt.field_names(language)
    assert names == ["a\\.b", "a", "a.b", "c", "c.d\\.e"]
    assert smt.build(language, {"a\\.b": 1, "a.b": 2, "a": True, "c": True,
                                "c.d\\.e": 3}) == {"a.b": 1, "a": {"b": 2}, "c": {"d.e": 3}}


@pytest.mark.parametrize("name", NAMES)
def test_a_float_bound_and_a_built_record_read_a_field_by_its_own_name(name):
    older = adapt_row({"type": "object", "properties": {name: {"type": "number", "maximum": 1.0}},
                       "required": [name]})
    newer = adapt_row({"type": "object",
                       "properties": {name: {"type": "number", "exclusiveMaximum": 1.0}},
                       "required": [name]})
    (spelled,) = smt.field_names(older)
    _, edge = smt._float_line(older, newer, smt._a_member(older))
    assert edge == {spelled: 1.0}
    assert smt.build(older, {spelled: 1.0}) == {name: 1.0}


@pytest.mark.parametrize("name", ["é", "a b", "a|b", "a\\b", "a\nb", "a\x00b", "", "\U0001F600"])
def test_the_solver_text_of_an_encoding_reads_back(name):
    enc = smt.MembershipEncoding(z3)
    solver = z3.Solver()
    solver.add(enc.V.is_absent(enc.var(name)), enc.V.is_absent(enc.var("plain")))
    again = z3.Solver()
    again.from_string(solver.to_smt2())
    assert again.check() == z3.sat
    assert all(str(v).replace("_", "").isalnum() for v in enc.vars.values())


def test_a_witness_is_nested_by_the_shape_that_admits_it():
    scalar = closed({"a": {"enum": [1]}})
    loose = closed({"a": {"type": "object", "properties": {"c": {"enum": [1]}}}})
    tight = closed({"a": {"type": "object", "properties": {"c": {"enum": [1]}},
                          "required": ["c"]}})

    def union(*shapes):
        return UnionLanguage("u", tuple(adapt_row(s) for s in shapes),
                             lambda v: next((i for i, s in enumerate(shapes) if valid(s, v)),
                                            None))
    result = smt._schema_inclusion(union(scalar, loose), union(scalar, tight))
    assert result.verdict == "falsified", result
    assert any(valid(s, result.witness) for s in (scalar, loose))
    assert not any(valid(s, result.witness) for s in (scalar, tight))


def test_a_dotted_field_a_closed_newer_record_does_not_declare_is_refused_by_it():
    result = smt._schema_inclusion(closed({"a.b": {"enum": [1]}}), closed({"c": {"enum": [1]}}, []))
    assert result.verdict == "falsified", result
    assert result.witness == {"a.b": 1}
