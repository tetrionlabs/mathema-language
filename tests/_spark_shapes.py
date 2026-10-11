# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Spark functions, one per construct the lowering reads, for the tests
that lower them and that run them in Spark. Each sets the column `out`
from the columns `x` (a double, may be null or NaN), `n` (an integer,
may be null) and `s` (a string, may be null)."""
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.functions import coalesce, col, isnan, lit, when

LIMIT = 10


def bands(df: DataFrame) -> DataFrame:
    return df.withColumn("out", when(col("x") < 0, "neg").when(col("x") <= LIMIT, "low")
                         .otherwise("high"))


def no_otherwise(df: DataFrame) -> DataFrame:
    return df.withColumn("out", when(col("x") > 5, lit(1)))


def null_check(df: DataFrame) -> DataFrame:
    return df.withColumn("out", F.when(F.col("n").isNull(), "none")
                         .when(F.col("n").isNotNull() & (F.col("n") >= 3), "big").otherwise("small"))


def negation_and_or(df: DataFrame) -> DataFrame:
    return df.withColumn("out", when(~(col("x") < 1) | (col("n") == 2), "yes").otherwise("no"))


def membership(df: DataFrame) -> DataFrame:
    return df.withColumn("out", when(col("s").isin("a", "b"), "ab")
                         .when(col("n").between(1, 4), "mid").otherwise("other"))


def arithmetic(df: DataFrame) -> DataFrame:
    return df.withColumn("out", when(col("x") * 2 + col("n") > 10, col("n") - 1).otherwise(col("x")))


def equality(df: DataFrame) -> DataFrame:
    return df.withColumn("out", when(col("x") == col("x"), "same").otherwise("differs"))


def first_present(df: DataFrame) -> DataFrame:
    return df.withColumn("out", coalesce(col("n"), lit(-1)))


def by_attribute(df: DataFrame) -> DataFrame:
    return df.withColumn("out", when(df.x >= 1.5, df["n"]).otherwise(0))


def chained(df: DataFrame) -> DataFrame:
    return df.withColumn("doubled", col("n") * 2).withColumn("out", when(col("x") < 0, "neg").otherwise("pos"))


def a_cast(df: DataFrame) -> DataFrame:
    return df.withColumn("out", col("x").cast("int"))


def reads_its_own_column(df: DataFrame) -> DataFrame:
    return df.withColumn("doubled", col("n") * 2).withColumn("out", when(col("doubled") > 4, "big"))


def nan_tested(df: DataFrame) -> DataFrame:
    return df.withColumn("out", when(isnan(col("x")), "bad").when(col("x") > 4, "high").otherwise("normal"))


# ---- shapes for the hole report: each null pitfall, and how it is handled


def hole_explicit(df: DataFrame) -> DataFrame:
    return df.withColumn("out", when(col("x").isNull() | (col("x") < 0), "Invalid")
                         .when(col("x") < 5, "low").otherwise("high"))


def hole_falls_through(df: DataFrame) -> DataFrame:
    return df.withColumn("out", when(col("x") < 0, "Invalid").when(col("x") < 5, "low").otherwise("high"))


def hole_not_equal(df: DataFrame) -> DataFrame:
    return df.withColumn("out", when(col("s") != "a", "other").otherwise("is a"))


def hole_negated(df: DataFrame) -> DataFrame:
    return df.withColumn("out", when(~(col("s") == "a"), "not a").otherwise("is a"))


def hole_arithmetic(df: DataFrame) -> DataFrame:
    return df.withColumn("out", when(col("x") * col("n") > 10, "big").otherwise("small"))


def hole_nan_above(df: DataFrame) -> DataFrame:
    return df.withColumn("out", when(col("x").isNull(), "unknown").when(col("x") > 4, "high").otherwise("normal"))


def hole_no_otherwise(df: DataFrame) -> DataFrame:
    return df.withColumn("out", when(col("x") > 5, lit(1)))


def hole_filled(df: DataFrame) -> DataFrame:
    return df.withColumn("out", coalesce(col("n"), lit(0)))


def hole_conditional(df: DataFrame) -> DataFrame:
    return df.withColumn("out", when(col("x").isNull() & (col("n") > 0), "a").otherwise("b"))


#: every shape the lowering reads, run against Spark by the agreement test
READ = ("bands", "no_otherwise", "null_check", "negation_and_or", "membership",
        "arithmetic", "equality", "first_present", "by_attribute", "chained", "nan_tested")
