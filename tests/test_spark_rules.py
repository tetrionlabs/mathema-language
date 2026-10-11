# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A column a Spark function computes is lowered, from the function's
source and without pyspark, to a Python function of the columns it
reads, with Spark's handling of null and NaN written in. The lowered
banding rule is proven band by band and its off-by-one variant is
falsified at the edge. A construct outside the subset is refused by
name. Where pyspark and Java are installed, every lowered function gives
what Spark gives, on rows that include null, NaN and the edges."""
import importlib.util
import math
import os
import random
import shutil
import sys
from pathlib import Path

import pytest

from mathema_language.spark import NotRead, rule

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
SHAPES = "tests._spark_shapes"


@pytest.fixture(autouse=True)
def _shop_on_path():
    if str(EXAMPLES) not in sys.path:
        sys.path.insert(0, str(EXAMPLES))


def test_the_lowering_needs_no_pyspark():
    r = rule("shop.spend.classify_po_category", "po_category")
    assert r.columns == {"po_value": "po_value"}
    assert r(None) == "Invalid" and r(-1) == "Invalid" and r(999.99) == "Micro"
    assert r(10000) == "Strategic" and r(50000) == "Major"
    assert r(float("nan")) == "Major"


def _verdict(fn, law):
    from mathema.conjecture import check_conjectures, claim
    (p,) = check_conjectures(fn, [claim(law)])
    return p


def test_the_banding_rule_is_proven_and_its_off_by_one_falsified_at_the_edge():
    good = rule("shop.spend.classify_po_category", "po_category", float_columns=set())
    bad = rule("shop.spend.classify_po_category_bug", "po_category", float_columns=set())
    bands = [("[0, 999.99]", "Micro"), ("[1000, 9999.99]", "Standard"),
             ("[10000, 49999.99]", "Strategic"), ("[50000, 1e12]", "Major"), ("[-1e12, -0.01]", "Invalid")]
    for interval, band in bands:
        p = _verdict(good, f'for po_value in {interval}, f(po_value) == "{band}"')
        assert (p.verdict, p.route) == ("proven", "derive"), (band, p.note)
    assert _verdict(good, 'f(None) == "Invalid"').verdict == "proven"
    p = _verdict(bad, 'for po_value in [10000, 49999.99], f(po_value) == "Strategic"')
    assert p.verdict == "falsified" and p.counterexample.startswith("po_value = 10000")


@pytest.mark.parametrize(("name", "fragment"), [
    ("a_cast", "cast"),
    ("reads_its_own_column", "computes ('doubled')"),
])
def test_a_construct_outside_the_subset_is_refused_by_name(name, fragment):
    with pytest.raises(NotRead, match=fragment.replace("(", r"\(").replace(")", r"\)")):
        rule(f"{SHAPES}.{name}", "out")


def test_a_column_the_function_does_not_set_is_refused():
    with pytest.raises(NotRead, match="sets no column 'missing'"):
        rule(f"{SHAPES}.bands", "missing")


def test_the_page_shows_the_module_as_it_is():
    page = (Path(__file__).resolve().parents[1] / "docs" / "how-to-prove-a-spark-rule.md").read_text()
    source = (EXAMPLES / "shop" / "spend.py").read_text()
    shown = page.split('```python title="examples/shop/spend.py"\n', 1)[1].split("```", 1)[0]
    assert shown in source


def _session():
    """A local Spark session whose Python workers run this interpreter."""
    from pyspark.sql import SparkSession
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
    return (SparkSession.builder.master("local[1]").appName("mathema-language-tests")
            .config("spark.ui.enabled", "false").config("spark.sql.shuffle.partitions", "1")
            .getOrCreate())


def _rows(rng):
    edges = [None, float("nan"), -1.0, 0.0, 0.5, 1.0, 1.5, 4.0, 5.0, 5.5, 10.0, 10.5, 11.0, -0.0]
    for _ in range(150):
        yield {"x": rng.choice(edges + [rng.uniform(-20, 20)]),
               "n": rng.choice([None, -1, 0, 1, 2, 3, 4, 5, 9]),
               "s": rng.choice([None, "a", "b", "c", ""])}


def _same(a, b):
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b and type(a) is type(b) if isinstance(a, bool) or isinstance(b, bool) else a == b


@pytest.mark.skipif(importlib.util.find_spec("pyspark") is None, reason="needs pyspark")
@pytest.mark.skipif(shutil.which("java") is None and not os.environ.get("JAVA_HOME"),
                    reason="needs a Java runtime for a Spark session")
def test_every_lowered_function_gives_what_spark_gives():
    from pyspark.sql import types as T

    import tests._spark_shapes as shapes
    spark = _session()
    schema = T.StructType([T.StructField("x", T.DoubleType(), True),
                           T.StructField("n", T.IntegerType(), True),
                           T.StructField("s", T.StringType(), True)])
    rows = list(_rows(random.Random(7)))
    frame = spark.createDataFrame(rows, schema)
    for name in shapes.READ:
        lowered = rule(f"{SHAPES}.{name}", "out")
        got = [r["out"] for r in getattr(shapes, name)(frame).collect()]
        for row, spark_value in zip(rows, got, strict=True):
            mine = lowered(**{var: row[column] for var, column in lowered.columns.items()})
            assert _same(mine, spark_value), (name, row, mine, spark_value)


@pytest.mark.skipif(importlib.util.find_spec("pyspark") is None, reason="needs pyspark")
@pytest.mark.skipif(shutil.which("java") is None and not os.environ.get("JAVA_HOME"),
                    reason="needs a Java runtime for a Spark session")
def test_spark_bands_the_edge_as_the_lowered_rule_does():
    from decimal import Decimal

    import shop.spend as spend
    from pyspark.sql import types as T
    spark = _session()
    schema = T.StructType([T.StructField("po_value", T.DecimalType(18, 2), True)])
    values = [None, Decimal("-0.01"), Decimal("0"), Decimal("999.99"), Decimal("1000"),
              Decimal("9999.99"), Decimal("10000"), Decimal("49999.99"), Decimal("50000")]
    frame = spark.createDataFrame([(v,) for v in values], schema)
    for name in ("classify_po_category", "classify_po_category_bug"):
        lowered = rule(f"shop.spend.{name}", "po_category", float_columns=set())
        got = [r["po_category"] for r in getattr(spend, name)(frame).collect()]
        assert got == [lowered(v) for v in values], name
    edited = [r["po_category"] for r in spend.classify_po_category_bug(frame).collect()]
    assert edited[values.index(Decimal("10000"))] == "Standard"
