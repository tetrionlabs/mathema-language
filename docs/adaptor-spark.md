<!-- github-only -->
> This page is part of the mathema documentation, [read it on the site](https://mathema.tetrionlabs.com/language/reference/adaptor-spark/).
<!-- /github-only -->

# Spark schemas

<!-- shop: procurement -->

The Spark adaptor reads a `pyspark.sql.types.StructType`, or the JSON
Spark writes for one, and its members are dicts shaped like
`Row.asDict(recursive=True)`. It never imports pyspark: a `StructType`
is read through its own `jsonValue()`, and the JSON form is plain data,
so a schema kept in a file, or the `schemaString` of a Delta table's
log, reads the same way with nothing installed. Membership is the
neutral checker's reading of the schema. Spark is not consulted, and
the record says the adaptor is `spark`.

## What it reads

| Spark type | Neutral model | Notes |
|---|---|---|
| `ByteType`, `ShortType`, `IntegerType`, `LongType` | `int8`, `int16`, `int32`, `int64` | a value past the width is outside |
| `FloatType`, `DoubleType` | `float32`, `float64` | NaN is a member, as it is in Spark |
| `DecimalType(p, s)` | `decimal(p, s)` | at most `s` places after the point and `p - s` digits before it; `DecimalType()` is `decimal(10, 0)` |
| `StringType`, and `CharType(n)`, `VarcharType(n)` | `string` | a CHAR or VARCHAR length is read from the field's metadata |
| `BooleanType`, `BinaryType`, `DateType` | `bool`, `binary`, `date` | |
| `TimestampType`, `TimestampNTZType` | `datetime` | naive, as `collect()` returns it |
| `ArrayType`, `MapType` | `list`, `map` | `containsNull` and `valueContainsNull` say whether an item may be null |
| a nested `StructType` | a struct of its fields | a dict in a member |
| `nullable=True` | the field may hold `None` | |
| any other type | `any` | named in the schema the record shows |

A Spark schema states types and nullability, not ranges, so nothing in
it bounds a price from below. A claim that needs a bound states it on
a path.

## A worked claim

A purchase order as the procurement pipeline reads it, from
`examples/shop/procurement.py`. The schema is the JSON the pipeline
passes to `spark.read.schema(StructType.fromJson(PURCHASE_ORDER))`:

```python
PURCHASE_ORDER = {
    "type": "struct",
    "fields": [
        {"name": "po_id", "type": "string", "nullable": False, "metadata": {}},
        {"name": "quantity", "type": "integer", "nullable": False, "metadata": {}},
        {"name": "unit_price", "type": "decimal(10,2)", "nullable": False, "metadata": {}},
        {"name": "po_value", "type": "decimal(18,2)", "nullable": True, "metadata": {}},
    ],
}


def line_total(po: dict) -> Decimal:
    """What the order's lines come to."""
    return po["quantity"] * po["unit_price"]
```

The same schema as a `StructType` reads identically:

```python title="the same schema, as pyspark writes it"
StructType([
    StructField("po_id", StringType(), False),
    StructField("quantity", IntegerType(), False),
    StructField("unit_price", DecimalType(10, 2), False),
    StructField("po_value", DecimalType(18, 2), True),
])
```

```text
f = line_total
for po in L[shop.procurement.PURCHASE_ORDER], po.quantity in [0, 100], po.unit_price in [0, 99.99], f(po) <= 9999
    proven

for po in L[shop.procurement.PURCHASE_ORDER], f(po) >= 0
    falsified   po = {'po_id': '', 'quantity': 1, 'unit_price': Decimal('-0.01'), 'po_value': Decimal('0')}: Decimal('-0.01') vs 0
```

The first is proven from the bounds the claim puts on the two fields.
The second is falsified because the schema allows a negative price: a
`decimal(10, 2)` holds -0.01 as readily as 0.01.

## Enforcing the schema

```python
def spend_band(po: dict) -> str:
    """The spend band a purchase order is reported under."""
    value = po["po_value"]
    if value is None or value < 0:
        return "Invalid"
    if value < 1000:
        return "Micro"
    if value < 10000:
        return "Standard"
    if value < 50000:
        return "Strategic"
    return "Major"
```

```text
f = spend_band
for po in L[shop.procurement.PURCHASE_ORDER], po.po_value in {absent}, f(po) == "Invalid"
    holds

for po in L[shop.procurement.PURCHASE_ORDER], excluded_outside_domain(po)
    falsified   po = {'po_id': '', 'quantity': 0, 'unit_price': Decimal('0.001'), 'po_value': Decimal('0')} (outside L[shop.procurement.PURCHASE_ORDER] at .unit_price: decimal(10, 2): at most 2 places after the point…
```

A price of 0.001 has one place more than `decimal(10, 2)` holds, and
`spend_band` banded the order anyway. That is fine for a function that
only ever sees rows Spark has already read, and the claim is the one
to write for the function that reads the order in, before anything is
banded.
