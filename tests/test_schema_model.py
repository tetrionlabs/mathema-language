# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The neutral schema model: types render, constraints render, a
schema refuses what it cannot mean, a decimal holds its precision and
scale at any width, list items are null only where the type allows,
and the JSON Schema of a row or a table carries every constraint the
model holds."""
import decimal

import pytest

from mathema_language.schema import (
    Constraints,
    Field,
    NeutralType,
    RowSchema,
)
from mathema_language.schema.checks import field_problems, json_schema


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


def test_the_json_schema_of_a_record():
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


def test_a_decimal_holds_its_precision_and_scale():
    price = Field("price", NeutralType("decimal", precision=5, scale=2))
    assert price.type.decimal_bound() == decimal.Decimal("999.99")
    assert field_problems(decimal.Decimal("999.99"), price) == []
    assert field_problems(decimal.Decimal("1.500"), price) == []
    assert field_problems(7, price) == []
    for value, predicate in [(decimal.Decimal("1000.00"), "decimal(5, 2): at most 999.99"),
                             (decimal.Decimal("1.005"), "decimal(5, 2): at most 2 places after the point"),
                             (decimal.Decimal("NaN"), "a finite decimal(5, 2)")]:
        assert [p.predicate for p in field_problems(value, price)] == [predicate]
    unbounded = Field("x", NeutralType("decimal"))
    assert unbounded.type.decimal_bound() is None
    assert field_problems(decimal.Decimal("1E40"), unbounded) == []


def test_null_items_only_where_the_type_allows_them():
    strict = Field("xs", NeutralType("list", item=NeutralType("int")))
    loose = Field("xs", NeutralType("list", item=NeutralType("int"), nullable_items=True))
    assert field_problems([1, None], strict) != []
    assert field_problems([1, None], loose) == []


def test_a_wide_decimal_is_exact_past_the_default_context():
    wide = Field("x", NeutralType("decimal", precision=38, scale=0))
    assert wide.type.decimal_bound() == decimal.Decimal("9" * 38)
    assert field_problems(decimal.Decimal("9" * 38), wide) == []
    assert field_problems(decimal.Decimal("1" + "0" * 38), wide) != []
    scaled = Field("x", NeutralType("decimal", precision=38, scale=10))
    assert field_problems(decimal.Decimal("1" * 28 + "." + "1" * 10), scaled) == []
    assert field_problems(decimal.Decimal("1" * 28 + "." + "1" * 11), scaled) != []
