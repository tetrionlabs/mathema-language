# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The Spark adaptor reads a `StructType`, or the JSON Spark writes for
one, into the neutral model without importing pyspark: each Spark type
to its neutral type, nullability, a CHAR or VARCHAR length, nullable
array items and map values. Members are dicts checked by the neutral
checker, and the lift reads their numeric fields. Where pyspark is
installed, the JSON this test states is the JSON pyspark writes."""
import decimal
import random

import pytest

from mathema_language.conformance import (
    foreign_object_problems,
    record_adaptor_problems,
)
from mathema_language.schema.adaptors.spark import adapt, schema_of, type_of

ORDER = {
    "type": "struct",
    "fields": [
        {"name": "po_id", "type": "string", "nullable": False, "metadata": {}},
        {"name": "quantity", "type": "integer", "nullable": False, "metadata": {}},
        {"name": "unit_price", "type": "decimal(10,2)", "nullable": False, "metadata": {}},
        {"name": "po_value", "type": "decimal(18,2)", "nullable": True, "metadata": {}},
        {"name": "tags", "type": {"type": "array", "elementType": "string", "containsNull": True},
         "nullable": True, "metadata": {}},
        {"name": "supplier_code", "type": "string", "nullable": True,
         "metadata": {"__CHAR_VARCHAR_TYPE_STRING": "varchar(8)"}},
    ],
}


def test_passes_the_conformance_checks():
    assert record_adaptor_problems(ORDER, adapt=adapt) == []
    assert type(adapt(ORDER).ecosystem).__name__ == "SparkEcosystem"


def test_returns_none_for_other_objects():
    assert foreign_object_problems(adapt) == []
    assert adapt({"type": "object", "properties": {"a": {"type": "integer"}}}) is None


@pytest.mark.parametrize(("spark", "neutral", "nan_allowed"), [
    ("byte", "int8", False),
    ("short", "int16", False),
    ("integer", "int32", False),
    ("long", "int64", False),
    ("float", "float32", True),
    ("double", "float64", True),
    ("decimal(18,2)", "decimal(18, 2)", False),
    ("decimal", "decimal(10, 0)", False),
    ("string", "string", False),
    ("boolean", "bool", False),
    ("binary", "binary", False),
    ("date", "date", False),
    ("timestamp", "datetime", False),
    ("timestamp_ntz", "datetime", False),
    ("variant", "any", False),
    ({"type": "array", "elementType": "long", "containsNull": False}, "list[int64]", False),
    ({"type": "map", "keyType": "string", "valueType": "double", "valueContainsNull": True},
     "map[string, float64]", False),
])
def test_each_spark_type_has_its_neutral_type(spark, neutral, nan_allowed):
    t, nan = type_of(spark)
    assert (t.render(), nan) == (neutral, nan_allowed)


def test_nullability_and_a_varchar_length_are_read():
    fields = {f.name: f for f in schema_of(ORDER).fields}
    assert not fields["quantity"].nullable and fields["po_value"].nullable
    assert fields["supplier_code"].constraints.max_len == 8
    assert fields["tags"].type.nullable_items


def _row(**changes):
    row = {"po_id": "PO-1", "quantity": 3, "unit_price": decimal.Decimal("12.50"),
           "po_value": decimal.Decimal("37.50"), "tags": ["urgent", None], "supplier_code": None}
    row.update(changes)
    return row


def test_a_member_and_each_way_a_record_leaves_the_language():
    language = adapt(ORDER)
    assert language.explain(_row()) is None
    cases = {
        "unit_price": (decimal.Decimal("12.505"), "decimal(10, 2): at most 2 places after the point"),
        "po_value": (decimal.Decimal("1E16"), "decimal(18, 2): at most 9999999999999999.99"),
        "quantity": (2 ** 31, "int32"),
        "supplier_code": ("ABCDEFGHI", "len <= 8"),
        "po_id": (None, "not null"),
    }
    for field, (value, predicate) in cases.items():
        problems = language.explain(_row(**{field: value}))
        assert [(p.path, p.predicate) for p in problems] == [(f".{field}", predicate)], field


def test_a_trailing_zero_past_the_scale_is_still_a_member():
    assert adapt(ORDER).explain(_row(unit_price=decimal.Decimal("12.500"))) is None


def test_null_array_items_follow_contains_null():
    strict = {"type": "struct", "fields": [
        {"name": "tags", "type": {"type": "array", "elementType": "string", "containsNull": False},
         "nullable": False, "metadata": {}}]}
    assert adapt(ORDER).explain(_row(tags=[None])) is None
    assert adapt(strict).explain({"tags": [None]}) is not None


def test_the_hazards_reach_the_decimal_edges_and_the_outside_one_place_past():
    language = adapt(ORDER)
    prices = {h.value["unit_price"] for h in language.hazards()}
    assert {decimal.Decimal("99999999.99"), decimal.Decimal("0.01")} <= prices
    rng = random.Random(0)
    outsides = [language.outside(rng) for _ in range(40)]
    assert any(o is not None and o.get("unit_price") == decimal.Decimal("0.001") for o in outsides)


def test_every_drawn_member_is_a_member():
    language = adapt(ORDER)
    rng = random.Random(1)
    for _ in range(200):
        assert language.explain(language.sample(rng)) is None


def line_total(po: dict) -> decimal.Decimal:
    """What the order's lines come to."""
    return po["quantity"] * po["unit_price"]


def test_the_lift_reads_the_fields_through_this_adaptor():
    from mathema.conjecture import check_conjectures, claim
    S = "L[tests.test_adaptor_spark.ORDER]"
    (bounded,) = check_conjectures(line_total, [claim(
        f"for po in {S}, po.quantity in [0, 100], po.unit_price in [0, 99.99], f(po) <= 9999")])
    assert (bounded.verdict, bounded.route) == ("proven", "derive")
    (unbounded,) = check_conjectures(line_total, [claim(f"for po in {S}, f(po) >= 0")])
    assert unbounded.verdict == "falsified"


def test_the_json_is_the_json_pyspark_writes():
    types = pytest.importorskip("pyspark.sql.types")
    struct = types.StructType([
        types.StructField("po_id", types.StringType(), False),
        types.StructField("quantity", types.IntegerType(), False),
        types.StructField("unit_price", types.DecimalType(10, 2), False),
        types.StructField("po_value", types.DecimalType(18, 2), True),
        types.StructField("tags", types.ArrayType(types.StringType(), True), True),
        types.StructField("supplier_code", types.StringType(), True,
                          {"__CHAR_VARCHAR_TYPE_STRING": "varchar(8)"}),
    ])
    assert struct.jsonValue() == ORDER
    assert schema_of(struct) == schema_of(ORDER)
    assert adapt(struct) is not None
