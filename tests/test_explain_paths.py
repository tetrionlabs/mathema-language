# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The explain path grammar, pinned: `""` the value, `.col` a column,
`[i]` a row or an item, `[i].col` a cell, `key(a, b)` a duplicated
key, `fk(col)->parent` an orphan, `rows` the count, `order(col)` a
sort violation, and nested paths compose."""
import math

from mathema_language.schema import (
    Constraints,
    Field,
    ForeignKey,
    NeutralType,
    PlainEcosystem,
    RowSchema,
    TableSchema,
)

ROW = RowSchema("Order", (
    Field("id", NeutralType("int")),
    Field("qty", NeutralType("int"), constraints=Constraints(min=1)),
    Field("price", NeutralType("float")),
    Field("tags", NeutralType("list", item=NeutralType("string"))),
    Field("ship", NeutralType("struct", fields=(Field("city", NeutralType("string")),)), nullable=True),
))
TABLE = TableSchema(ROW, primary_key=("id",), row_count=(1, 3), ordered=("id",),
                    foreign_keys=(ForeignKey(("qty",), "stock", ("level",)),))
ECO = PlainEcosystem()


def _paths(problems):
    return [(p.path, p.predicate) for p in problems]


def _row(**over):
    base = {"id": 1, "qty": 2, "price": 1.0, "tags": [], "ship": None}
    base.update(over)
    return base


def test_row_paths():
    assert _paths(ECO.validate_row(ROW, _row(qty=0))) == [(".qty", ">= 1")]
    assert _paths(ECO.validate_row(ROW, _row(price=math.nan))) == [(".price", "not nan")]
    assert _paths(ECO.validate_row(ROW, _row(tags=["a", 3]))) == [(".tags[1]", "string")]
    assert _paths(ECO.validate_row(ROW, _row(ship={"city": 5}))) == [(".ship.city", "string")]
    missing = _row()
    del missing["id"]
    assert _paths(ECO.validate_row(ROW, missing)) == [(".id", "present")]
    assert _paths(ECO.validate_row(ROW, _row(extra=1))) == [(".extra", "a column of the schema")]
    assert _paths(ECO.validate_row(ROW, "not a row")) == [("", "a mapping record")]


def test_table_paths():
    assert _paths(ECO.validate_frame(TABLE, [])) == [("rows", ">= 1")]
    assert _paths(ECO.validate_frame(TABLE, [_row(id=i) for i in range(4)])) == [("rows", "<= 3")]
    assert _paths(ECO.validate_frame(TABLE, [_row(), _row(id=2, qty=0)])) == [("[1].qty", ">= 1")]
    assert _paths(ECO.validate_frame(TABLE, [_row(id=1), _row(id=1)])) == [("key(id)", "unique")]
    assert _paths(ECO.validate_frame(TABLE, [_row(id=2), _row(id=1)])) == [("order(id)", "sorted")]
    parents = {"stock": [{"level": 2}]}
    assert _paths(ECO.validate_frame(TABLE, [_row(qty=5)], parents)) == [("fk(qty)->stock", "a key of the parent")]
    assert ECO.validate_frame(TABLE, [_row(qty=2)], parents) == []
