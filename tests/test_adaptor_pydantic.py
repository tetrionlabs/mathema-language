# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The pydantic adaptor passes the conformance checks, returns None for
anything that is not a model class, and decides membership with the
model's own `model_validate`, so a non-member is explained in pydantic's words."""
import pytest

pydantic = pytest.importorskip("pydantic")

from mathema_language.conformance import (  # noqa: E402
    foreign_object_problems,
    record_adaptor_problems,
)
from mathema_language.schema.adaptors.pydantic import adapt  # noqa: E402
from tests._pydantic_shapes import OrderModel  # noqa: E402


def test_passes_the_conformance_checks():
    assert record_adaptor_problems(OrderModel, adapt=adapt) == []
    language = adapt(OrderModel)
    assert type(language.ecosystem).__name__ == "PydanticEcosystem"


def test_returns_none_for_other_objects():
    assert foreign_object_problems(adapt) == []


def test_a_non_member_is_explained_in_pydantic_s_words():
    language = adapt(OrderModel)
    row = OrderModel.model_construct(id=1, qty=0, price=-1.0, sku="abc", kind="web", note=None)
    assert [(p.path, p.predicate) for p in language.explain(row)] == [
        (".qty", "Input should be greater than or equal to 1"),
        (".price", "Input should be greater than or equal to 0"),
    ]


def test_extra_forbid_is_the_exact_column_policy():
    assert adapt(OrderModel).schema.column_policy == "exact"


def _lift_verdict(fn, law):
    from mathema.conjecture import check_conjectures, claim
    (p,) = check_conjectures(fn, [claim(law)])
    assert "UNCORROBORATED" not in (p.note or ""), p.note
    return p.verdict


def total(row) -> float:
    """Quantity times price."""
    return row.qty * row.price


def width(row) -> int:
    """The columns the sku takes, with a space either side."""
    return len(row.sku) + 2


def test_the_lift_reads_the_fields_through_this_adaptor():
    assert _lift_verdict(total, "for row in L[tests._pydantic_shapes.OrderModel], f(row) >= 0") == "proven"
    assert _lift_verdict(width, "for row in L[tests._pydantic_shapes.OrderModel], f(row) <= 10") == "proven"
    assert _lift_verdict(width, "for row in L[tests._pydantic_shapes.OrderModel], f(row) <= 9") == "falsified"
