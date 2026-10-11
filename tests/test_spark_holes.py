# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""For each input column of a Spark rule and each hole it admits, the
report says what the rule writes and how: explicit when a branch tests
for the hole, implicit when Spark's semantics decided it (a fall-through
to `otherwise`, NaN above every number, null through arithmetic),
conditional when it depends on another column. Where pyspark and Java
are installed, every reported outcome is what Spark writes, whatever the
other columns hold."""
import importlib.util
import itertools
import math
import os
import shutil
import sys

import pytest

from mathema_language.spark import holes

SHAPES = "tests._spark_shapes"

#: the hole-report shapes, with the holes each input column admits
HOLES = {
    "hole_explicit": {"x": {"null", "nan"}},
    "hole_falls_through": {"x": {"null", "nan"}},
    "hole_not_equal": {"s": {"null"}},
    "hole_negated": {"s": {"null"}},
    "hole_arithmetic": {"x": {"null", "nan"}, "n": {"null"}},
    "hole_nan_above": {"x": {"null", "nan"}},
    "hole_no_otherwise": {"x": {"null", "nan"}},
    "hole_filled": {"n": {"null"}},
    "hole_conditional": {"x": {"null", "nan"}, "n": {"null"}},
    "nan_tested": {"x": {"null", "nan"}},
}

#: (shape, column, member) -> (how, output); output None is a null
EXPECTED = {
    ("hole_explicit", "x", "null"): ("explicit", "Invalid"),
    ("hole_explicit", "x", "nan"): ("implicit", "high"),
    ("hole_falls_through", "x", "null"): ("implicit", "high"),
    ("hole_falls_through", "x", "nan"): ("implicit", "high"),
    ("hole_not_equal", "s", "null"): ("implicit", "is a"),
    ("hole_negated", "s", "null"): ("implicit", "is a"),
    ("hole_arithmetic", "x", "null"): ("implicit", "small"),
    ("hole_arithmetic", "x", "nan"): ("conditional", None),
    ("hole_arithmetic", "n", "null"): ("implicit", "small"),
    ("hole_nan_above", "x", "null"): ("explicit", "unknown"),
    ("hole_nan_above", "x", "nan"): ("implicit", "high"),
    ("hole_no_otherwise", "x", "null"): ("implicit", None),
    ("hole_no_otherwise", "x", "nan"): ("implicit", 1),
    ("hole_filled", "n", "null"): ("explicit", 0),
    ("hole_conditional", "x", "null"): ("conditional", None),
    ("hole_conditional", "x", "nan"): ("implicit", "b"),
    ("hole_conditional", "n", "null"): ("conditional", None),
    ("nan_tested", "x", "null"): ("implicit", "normal"),
    ("nan_tested", "x", "nan"): ("explicit", "bad"),
}


def _report(shape):
    return holes(f"{SHAPES}.{shape}", "out", admits=HOLES[shape])


def test_every_hole_is_reported_with_how_it_was_handled():
    got = {}
    for shape in HOLES:
        for o in _report(shape):
            got[(shape, o.column, o.member)] = (o.how, None if o.how == "conditional" else o.output)
    assert got == EXPECTED


def test_the_record_sentence_says_why():
    (null, nan) = _report("hole_falls_through")
    assert null.sentence() == ("at x = null f gave 'high' (not handled: every condition is null or "
                               "false there (a comparison with null is null), so otherwise)")
    assert nan.because.startswith("every condition is false there (NaN compared as above every number)")
    (tested,) = [o for o in _report("hole_explicit") if o.member == "null"]
    assert tested.sentence() == "at x = null f gave 'Invalid' (handled in the code: isNull)"
    (passes,) = [o for o in _report("hole_no_otherwise") if o.member == "null"]
    assert passes.propagates


def test_a_conditional_outcome_lists_what_it_can_be():
    (x_null, _x_nan, n_null) = _report("hole_conditional")
    assert x_null.how == "conditional" and set(x_null.possible) == {"a", "b"}
    assert n_null.how == "conditional"


def _session():
    from pyspark.sql import SparkSession
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
    return (SparkSession.builder.master("local[1]").appName("mathema-language-holes")
            .config("spark.ui.enabled", "false").config("spark.sql.shuffle.partitions", "1")
            .getOrCreate())


def _same(a, b):
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b


@pytest.mark.skipif(importlib.util.find_spec("pyspark") is None, reason="needs pyspark")
@pytest.mark.skipif(shutil.which("java") is None and not os.environ.get("JAVA_HOME"),
                    reason="needs a Java runtime for a Spark session")
def test_every_reported_outcome_is_what_spark_writes():
    from pyspark.sql import types as T

    import tests._spark_shapes as shapes
    spark = _session()
    schema = T.StructType([T.StructField("x", T.DoubleType(), True),
                           T.StructField("n", T.IntegerType(), True),
                           T.StructField("s", T.StringType(), True)])
    others = {"x": [None, float("nan"), -1.0, 0.0, 3.0, 6.0, 20.0],
              "n": [None, -1, 0, 3, 9],
              "s": [None, "a", "b", ""]}
    hole_value = {"null": None, "nan": float("nan")}
    for shape in HOLES:
        for outcome in _report(shape):
            choices = {c: ([hole_value[outcome.member]] if c == outcome.column else vals)
                       for c, vals in others.items()}
            rows = [dict(zip(choices, combo, strict=True)) for combo in itertools.product(*choices.values())]
            written = [r["out"] for r in getattr(shapes, shape)(spark.createDataFrame(rows, schema)).collect()]
            if outcome.how == "conditional":
                assert all(any(_same(w, p) for p in outcome.possible) for w in written), (shape, outcome)
            else:
                assert all(_same(w, outcome.output) for w in written), (shape, outcome, set(map(str, written)))
