# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A member of a dataclass language is an instance of its class at
every level: a nested record given as a mapping is not a member (a
function reading `o.address.zip` would fail on it for a reason the
schema rules out), and no hazard or draw builds one. A TypedDict's
records are mappings, as its class says."""
import pytest

from mathema_language.schema.adaptors import adapt_row
from tests import _nested_orders as orders


def _records(value):
    stack, out = [value], []
    while stack:
        v = stack.pop()
        if isinstance(v, (list, tuple)):
            stack.extend(v)
        elif hasattr(v, "__dataclass_fields__"):
            out.append(v)
            stack.extend(vars(v).values())
        elif isinstance(v, dict):
            out.append(v)
            stack.extend(v.values())
    return out


def test_a_nested_mapping_is_not_a_dataclass_member():
    lang = adapt_row(orders.Order)
    bad = orders.Order(address={"zip": "1"})
    assert not lang.contains(bad)
    assert [p.path for p in lang.explain(bad)] == [".address"]
    assert not lang.contains({"address": orders.Address("1"), "lines": []})
    assert lang.contains(orders.Order(address=orders.Address("1")))


def test_every_hazard_and_draw_is_built_from_the_classes():
    import random
    lang = adapt_row(orders.Order)
    rng = random.Random(0)
    values = [h.value for h in lang.hazards()] + [lang.sample(rng) for _ in range(40)]
    for v in values:
        for record in _records(v):
            assert not isinstance(record, dict), v


def test_a_typeddict_s_records_are_mappings():
    lang = adapt_row(orders.OrderDict)
    assert lang.contains({"address": {"zip": "1"}})


def test_a_claim_on_a_nested_field_is_not_falsified_by_a_mapping():
    pytest.importorskip("mathema")
    from mathema.conjecture import check_conjectures, claim
    (p,) = check_conjectures(orders.zip_width, [claim(
        "for o in L[tests._nested_orders.Order], f(o) <= 5")])
    assert p.verdict in ("proven", "holds"), (p.verdict, p.counterexample)
