# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The neutral schema model: types render, constraints render, a
schema refuses what it cannot mean, and the JSON Schema of a row or
a table carries every constraint the model holds."""
import pytest

from mathema_language.schema import (
    Constraints,
    Field,
    NeutralType,
    RowSchema,
)
from mathema_language.schema.checks import json_schema
from mathema_language.schema.model import ForeignKey, TableSchema


def test_types_render():
    assert NeutralType("int", bits=64).render() == "int64"
    assert NeutralType("int", bits=8, signed=False).render() == "uint8"
    assert NeutralType("decimal", precision=10, scale=2).render() == "decimal(10, 2)"
    assert NeutralType("datetime", unit="ns", tz="UTC").render() == "datetime[ns, UTC]"
    assert NeutralType("categorical", levels=("a", "b")).render() == "categorical[a, b]"
    assert NeutralType("list", item=NeutralType("int")).render() == "list[int]"
    struct = NeutralType("struct", fields=(Field("x", NeutralType("float")),))
    assert struct.render() == "struct{x: float}"
    with pytest.raises(ValueError, match="unknown base type"):
        NeutralType("varchar")


def test_constraints_render_and_truth():
    assert not Constraints()
    assert Constraints(min=0, max=10).render() == "[0, 10]"
    assert Constraints(exclusive_min=0).render() == "(0, inf)"
    assert Constraints(min_len=1, max_len=80).render() == "len in [1, 80]"
    assert Constraints(enum=("a", "b")).render() == "one of {'a', 'b'}"
    assert Constraints(const=3).render() == "== 3"
    assert Constraints(multiple_of=5).low is None


def test_a_schema_refuses_what_it_cannot_mean():
    with pytest.raises(ValueError, match="duplicate field"):
        RowSchema("R", (Field("a", NeutralType("int")), Field("a", NeutralType("int"))))
    with pytest.raises(ValueError, match="column_policy"):
        RowSchema("R", (), column_policy="loose")
    row = RowSchema("R", (Field("id", NeutralType("int")),))
    with pytest.raises(ValueError, match="no column 'x'"):
        TableSchema(row, primary_key=("x",))
    with pytest.raises(ValueError, match="row_count"):
        TableSchema(row, row_count=(5, 2))


def test_the_json_schema_of_a_row_and_a_table():
    row = RowSchema("Order", (
        Field("id", NeutralType("int"), unique=True),
        Field("qty", NeutralType("int"), constraints=Constraints(min=1, max=10)),
        Field("sku", NeutralType("string"), constraints=Constraints(min_len=1, max_len=8, regex="[A-Z]+")),
        Field("note", NeutralType("string"), nullable=True, default=None),
        Field("kind", NeutralType("categorical", levels=("a", "b"))),
    ))
    js = json_schema(row)
    assert js["required"] == ["id", "qty", "sku", "kind"]
    assert js["additionalProperties"] is False
    assert js["properties"]["qty"] == {"type": "integer", "minimum": 1, "maximum": 10}
    assert js["properties"]["sku"] == {"type": "string", "minLength": 1, "maxLength": 8, "pattern": "[A-Z]+"}
    assert js["properties"]["note"] == {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None}
    assert js["properties"]["kind"] == {"enum": ["a", "b"]}
    assert js["properties"]["id"]["x-mathema"] == {"unique": True}
    table = TableSchema(row, primary_key=("id",), row_count=(1, 100),
                        foreign_keys=(ForeignKey(("kind",), "kinds", ("name",)),), ordered=("id",))
    tj = json_schema(table)
    assert tj["type"] == "array" and tj["minItems"] == 1 and tj["maxItems"] == 100
    assert tj["x-mathema"] == {"primary_key": ["id"], "ordered": ["id"],
                               "foreign_keys": [{"columns": ["kind"], "parent": "kinds",
                                                 "parent_columns": ["name"]}]}
