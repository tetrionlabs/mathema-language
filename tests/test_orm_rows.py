# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""ORM rows: a SQLAlchemy table's NOT NULL, UNIQUE, CHECK and FOREIGN
KEY are the database's verdicts, its keys become the frame's
defaults; a Django model's options and validators are `full_clean`'s
verdicts, a `ForeignKey` becomes the `<name>_id` column with a
foreign key to the parent."""
import random

import pytest

from mathema_language.schema import frame_of
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
    assert lang.table_defaults.primary_key == ("id",)
    problems = lang.explain({"id": 1, "qty": 0, "price": 1.0, "sku": "A", "kind": "web", "note": None})
    assert [(p.path, p.predicate) for p in problems] == [(".qty", ">= 1")]


def test_a_declarative_class_s_unique_set_and_foreign_key_are_the_database_s(sa_shapes):
    lines = adapt_row(sa_shapes.Line)
    defaults = lines.table_defaults
    assert defaults.unique == (("sku", "batch"),)
    assert defaults.foreign_keys[0].parent == "skus" and defaults.foreign_keys[0].columns == ("sku",)
    assert lines.schema.field("qty").constraints.exclusive_min == 0
    frame = frame_of(sa_shapes.Line, row_count=(1, 4))
    assert frame.table.primary_key == ("id",) and frame.table.unique == (("sku", "batch"),)
    rng = random.Random(3)
    for _ in range(20):
        assert frame.contains(frame.sample(rng))
    a, b = sa_shapes.Line(id=1, sku=1, batch=1, qty=1), sa_shapes.Line(id=2, sku=1, batch=1, qty=1)
    dup = frame.explain([a, b])
    assert dup and dup[0].path == "key(sku, batch)"
    parents = {"skus": [sa_shapes.Sku(code=1, name="x")]}
    assert frame.ecosystem.validate_frame(frame.table, [a], parents) == []
    orphan = frame.ecosystem.validate_frame(frame.table, [sa_shapes.Line(id=3, sku=9, batch=2, qty=1)], parents)
    assert orphan and orphan[0].path.startswith("fk(sku)")


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


def test_a_django_foreign_key_becomes_the_id_column_with_a_key_to_the_parent(dj_shapes):
    lines = adapt_row(dj_shapes.LineDj)
    assert "sku_id" in lines.schema.names
    fk = lines.table_defaults.foreign_keys[0]
    assert fk.columns == ("sku_id",) and fk.parent == "SkuDj" and fk.parent_columns == ("id",)
    assert lines.schema.field("qty").constraints.min == 0
    assert lines.schema.field("batch").constraints.regex is not None
    rng = random.Random(5)
    for _ in range(30):
        assert lines.contains(lines.sample(rng))
    frame = frame_of(dj_shapes.LineDj, row_count=(1, 3), parents={"SkuDj": dj_shapes.SkuDj})
    assert frame.table.foreign_keys == (fk,)
    for _ in range(10):
        assert frame.contains(frame.sample(rng))
