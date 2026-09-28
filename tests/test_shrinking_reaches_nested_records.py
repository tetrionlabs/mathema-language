# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Shrinking a record reaches the records nested in it, in a field or
in a list, and moves their fields to their simplest members too, so a
witness keeps only what the failure needs at every level."""
import pytest

from mathema_language.schema.adaptors import adapt_row
from tests import _nested_orders as orders


def test_a_nested_record_s_field_is_shrunk():
    lang = adapt_row(orders.Order)
    order = orders.Order(address=orders.Address("12345"), lines=[orders.OrderLine(qty=4)])
    candidates = list(lang.shrink(order))
    assert any(c.address.zip != "12345" and c.lines == order.lines for c in candidates)
    assert all(lang.contains(c) for c in candidates)


def test_a_record_in_a_list_is_shrunk():
    lang = adapt_row(orders.Order)
    order = orders.Order(address=orders.Address(None), lines=[orders.OrderLine(qty=4)])
    assert any(c.lines and c.lines[0].qty == 1 for c in lang.shrink(order))


def test_a_witness_is_simple_at_every_level():
    pytest.importorskip("mathema")
    from mathema.conjecture import check_conjectures, claim
    (p,) = check_conjectures(orders.largest_qty, [claim(
        "for o in L[tests._nested_orders.Order], f(o) <= 3")])
    assert p.verdict == "falsified"
    assert "Address(zip=None)" in p.counterexample or "Address(zip='')" in p.counterexample, \
        p.counterexample
    assert "OrderLine(qty=4)" in p.counterexample, p.counterexample


def test_a_field_at_its_simplest_offers_nothing_new():
    from mathema_language.schema import generate as g
    from mathema_language.schema.model import Field, NeutralType
    f = Field("n", NeutralType("int"))
    assert g.simpler(f, g.simplest(f)) == [g.simplest(f)]


def test_decimals_and_strings_step_toward_their_simplest():
    from decimal import Decimal

    from mathema_language.schema import generate as g
    from mathema_language.schema.model import Field, NeutralType
    price = Field("price", NeutralType("decimal", precision=10, scale=2))
    assert any(isinstance(v, Decimal) and 0 < v < Decimal("100.00")
               for v in g.simpler(price, Decimal("100.00")))
    sku = Field("sku", NeutralType("string"))
    steps = g.simpler(sku, "wb\U000f547cxy")
    assert "aaaaa" in steps and "wb" in steps and "wb\U000f547cx" in steps


def test_an_orm_witness_is_shrunk():
    pytest.importorskip("mathema")
    sa = pytest.importorskip("sqlalchemy")  # noqa: F841
    from mathema.conjecture import check_conjectures, claim

    from tests import _sqlalchemy_shapes as shapes
    (p,) = check_conjectures(shapes.order_total, [claim(
        "for order in L[tests._sqlalchemy_shapes.Order], f(order) <= 10000")])
    assert p.verdict == "falsified"
    assert p.meta["mathema.witness_shrunk"]["steps"] < 400, p.meta
    assert "sku='aaa'" in p.counterexample or "sku=''" in p.counterexample, p.counterexample
