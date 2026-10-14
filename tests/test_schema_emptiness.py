# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A field is empty when no value passes its own checker. `not_empty`
decides it from the field's description, the simplest member of an
empty field is None, a field whose bound its type cannot read has no
simplest member rather than a crash, and the model refuses descriptions
that cannot mean anything (a width, precision, scale or length out of
range)."""
import pytest

from mathema_language.schema.checks import field_problems
from mathema_language.schema.emptiness import not_empty
from mathema_language.schema.generate import simplest
from mathema_language.schema.model import Constraints, Field, NeutralType

EMPTY = [
    Field("a", NeutralType("int"), constraints=Constraints(min=5, max=3)),
    Field("a", NeutralType("int"), constraints=Constraints(min="x")),
    Field("a", NeutralType("string"), constraints=Constraints(const=None)),
    Field("a", NeutralType("binary"), constraints=Constraints(const=True)),
    Field("a", NeutralType("string"), constraints=Constraints(enum=())),
    Field("a", NeutralType("string"), constraints=Constraints(regex="[")),
    Field("a", NeutralType("string"), constraints=Constraints(min_len=3, max_len=2)),
    Field("a", NeutralType("int"), constraints=Constraints(min=1, max=3, multiple_of=4)),
    Field("a", NeutralType("categorical", levels=())),
    Field("a", NeutralType("decimal"), constraints=Constraints(multiple_of=0)),
]

NOT_EMPTY = [
    Field("a", NeutralType("int")),
    Field("a", NeutralType("string"), nullable=True, constraints=Constraints(const=None)),
    Field("a", NeutralType("string"), constraints=Constraints(regex="[0-9]{5}")),
    Field("a", NeutralType("string"), constraints=Constraints(regex="ab+", min_len=4)),
    Field("a", NeutralType("int"), constraints=Constraints(min=1, max=9, multiple_of=4)),
    Field("a", NeutralType("float"), constraints=Constraints(exclusive_min=0, exclusive_max=1)),
    Field("a", NeutralType("decimal", precision=4, scale=2), constraints=Constraints(min=10)),
    Field("a", NeutralType("list", item=NeutralType("int")), constraints=Constraints(min_len=2)),
]


@pytest.mark.parametrize("f", EMPTY, ids=lambda f: repr(f.constraints)[:60])
def test_an_empty_field_is_empty_and_its_simplest_member_is_none(f):
    assert not not_empty(f)
    assert simplest(f) is None


@pytest.mark.parametrize("f", NOT_EMPTY, ids=lambda f: f.type.base)
def test_a_field_with_members_is_not_empty_and_simplest_is_one(f):
    assert not_empty(f)
    assert field_problems(simplest(f), f) == []


@pytest.mark.parametrize("make", [
    lambda: NeutralType("int", bits=-5),
    lambda: NeutralType("int", bits=0),
    lambda: NeutralType("decimal", precision=0),
    lambda: NeutralType("decimal", precision=4, scale=5),
    lambda: NeutralType("decimal", scale=-1),
    lambda: Constraints(min_len=-1),
    lambda: Constraints(max_len=-3),
])
def test_a_description_that_cannot_mean_anything_is_refused(make):
    with pytest.raises(ValueError):
        make()


@pytest.mark.parametrize("value", [{}, 1, "x"])
def test_a_reference_with_no_definitions_to_resolve_it_is_a_problem(value):
    from mathema_language.schema.model import RowSchema
    ref = Field("a", NeutralType("ref", ref="Node"))
    assert field_problems(value, ref) != []
    assert field_problems(value, ref, definitions=RowSchema("Other", ())) != []
    assert field_problems(None, Field("a", NeutralType("ref", ref="Node"), nullable=True)) == []
