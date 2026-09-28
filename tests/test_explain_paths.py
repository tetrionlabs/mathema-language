# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The explain path grammar, pinned: `""` the value, `.col` a field,
`[i]` an item, and nested paths compose."""
import math

from mathema_language.schema import (
    Constraints,
    Field,
    NeutralType,
    PlainEcosystem,
    RowSchema,
)

ROW = RowSchema("Order", (
    Field("id", NeutralType("int")),
    Field("qty", NeutralType("int"), constraints=Constraints(min=1)),
    Field("price", NeutralType("float")),
    Field("tags", NeutralType("list", item=NeutralType("string"))),
    Field("ship", NeutralType("struct", fields=(Field("city", NeutralType("string")),)), nullable=True),
))
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
