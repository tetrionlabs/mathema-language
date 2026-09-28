# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The TypedDict adaptor passes the conformance checks, returns None for
anything that is not a TypedDict, and members are plain dicts checked
by the neutral checker, a missing required key included."""
from typing import Annotated, TypedDict

from annotated_types import Ge, Le, MaxLen

from mathema_language.conformance import (
    foreign_object_problems,
    record_adaptor_problems,
)
from mathema_language.schema.adaptors.typeddict import adapt


class LineDict(TypedDict):
    sku: Annotated[str, MaxLen(8)]
    qty: Annotated[int, Ge(1), Le(10)]
    price: Annotated[float, Ge(0.0)]


def test_passes_the_conformance_checks():
    assert record_adaptor_problems(LineDict, adapt=adapt) == []
    language = adapt(LineDict)
    assert type(language.ecosystem).__name__ == "PlainEcosystem"


def test_returns_none_for_other_objects():
    assert foreign_object_problems(adapt) == []


def test_a_missing_key_and_a_bound_are_explained():
    language = adapt(LineDict)
    problems = language.explain({"sku": "abcdefghij", "qty": 3})
    assert [(p.path, p.predicate) for p in problems] == [(".sku", "len <= 8"), (".price", "present")]


def _lift_verdict(fn, law):
    from mathema.conjecture import check_conjectures, claim
    (p,) = check_conjectures(fn, [claim(law)])
    assert "UNCORROBORATED" not in (p.note or ""), p.note
    return p.verdict


def total(row) -> float:
    """Quantity times price."""
    return row["qty"] * row["price"]


def width(row) -> int:
    """The columns the sku takes, with a space either side."""
    return len(row["sku"]) + 2


def test_the_lift_reads_the_fields_through_this_adaptor():
    assert _lift_verdict(total, "for row in L[tests.test_adaptor_typeddict.LineDict], f(row) >= 0") == "proven"
    assert _lift_verdict(width, "for row in L[tests.test_adaptor_typeddict.LineDict], f(row) <= 10") == "proven"
    assert _lift_verdict(width, "for row in L[tests.test_adaptor_typeddict.LineDict], f(row) <= 9") == "falsified"
