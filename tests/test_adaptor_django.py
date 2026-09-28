# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The Django adaptor passes the conformance checks, returns None for
anything that is not a model class, and leaves what the neutral model
cannot read to `full_clean`: a custom validator's message is the
explanation."""
import pytest

pytest.importorskip("django")

from mathema_language.conformance import (  # noqa: E402
    foreign_object_problems,
    row_adaptor_problems,
)
from mathema_language.schema.adaptors.django import adapt  # noqa: E402
from tests import _django_shapes as shapes  # noqa: E402


def test_passes_the_conformance_checks():
    assert row_adaptor_problems(shapes.OrderModelDj, adapt=adapt) == []
    language = adapt(shapes.OrderModelDj)
    assert type(language.ecosystem).__name__ == "DjangoEcosystem"


def test_returns_none_for_other_objects():
    assert foreign_object_problems(adapt) == []


def test_a_custom_validator_is_full_clean_s():
    language = adapt(shapes.CodedDj)
    assert language.contains(shapes.CodedDj(code="ABC"))
    assert [(p.path, p.predicate) for p in language.explain(shapes.CodedDj(code="abc"))] == [
        (".code", "code must be upper case")]


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
    assert _lift_verdict(total, "for row in L[tests._django_shapes.OrderModelDj], f(row) >= 0") == "proven"
    assert _lift_verdict(width, "for row in L[tests._django_shapes.OrderModelDj], f(row) <= 10") == "proven"
    assert _lift_verdict(width, "for row in L[tests._django_shapes.OrderModelDj], f(row) <= 9") == "falsified"
