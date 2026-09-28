# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""ORM records: a SQLAlchemy table's NOT NULL and CHECK are the
database's verdicts; a Django model's options and validators are
`full_clean`'s verdicts, and a `ForeignKey` is its `<name>_id`
column."""
import random

import pytest

from mathema_language.schema.adaptors import adapt_row


@pytest.fixture(scope="module")
def sa_shapes():
    return pytest.importorskip("tests._sqlalchemy_shapes")


@pytest.fixture(scope="module")
def dj_shapes():
    return pytest.importorskip("tests._django_shapes")


def test_a_table_s_check_constraint_is_read_as_bounds_and_held_by_the_database(sa_shapes):
    lang = adapt_row(sa_shapes.ORDERS_TABLE)
    surrogate = lang.explain({"id": 1, "qty": 1, "price": 1.0, "sku": "\ud800", "kind": "web", "note": None})
    assert [(p.path, p.predicate) for p in surrogate] == [(".sku", "encodable as UTF-8")]
    assert lang.schema.field("qty").constraints.min == 1
    assert lang.schema.field("qty").constraints.max == 10
    assert lang.schema.field("price").constraints.min == 0
    assert lang.schema.field("sku").constraints.max_len == 8
    assert lang.schema.field("kind").type.levels == ("web", "shop")
    problems = lang.explain({"id": 1, "qty": 0, "price": 1.0, "sku": "A", "kind": "web", "note": None})
    assert [(p.path, p.predicate) for p in problems] == [(".qty", ">= 1")]


def test_a_declarative_class_s_check_is_read_as_a_bound(sa_shapes):
    lines = adapt_row(sa_shapes.Line)
    assert lines.schema.field("qty").constraints.exclusive_min == 0
    rng = random.Random(3)
    for _ in range(20):
        assert lines.contains(lines.sample(rng))


def test_a_django_model_s_options_are_full_clean_s_verdicts(dj_shapes):
    lang = adapt_row(dj_shapes.OrderModelDj)
    names = lang.schema.names
    assert names == ("id", "qty", "price", "sku", "kind", "note")
    assert lang.schema.field("qty").constraints.min == 1 and lang.schema.field("qty").constraints.max == 10
    assert lang.schema.field("kind").type.levels == ("web", "shop")
    assert lang.schema.field("id").required is False and lang.schema.field("id").nullable
    row = dj_shapes.OrderModelDj(qty=11, price=1.0, sku="A", kind="web")
    problems = lang.explain(row)
    assert problems and problems[0].path == ".qty"
    assert lang.contains(dj_shapes.OrderModelDj(qty=2, price=1.0, sku="", kind="shop"))
    too_long = dj_shapes.OrderModelDj(qty=2, price=1.0, sku="ABCDEFGHI", kind="shop")
    assert [p.path for p in lang.explain(too_long)] == [".sku"]


def test_a_django_foreign_key_is_its_id_column(dj_shapes):
    lines = adapt_row(dj_shapes.LineDj)
    assert "sku_id" in lines.schema.names
    assert lines.schema.field("qty").constraints.min == 0
    assert lines.schema.field("batch").constraints.regex is not None
    rng = random.Random(5)
    for _ in range(30):
        assert lines.contains(lines.sample(rng))
