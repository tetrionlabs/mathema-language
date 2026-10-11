# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Spark functions, one per construct the lowering reads, for the tests
that lower them and that run them in Spark. Each sets the column `out`
from the columns `x` (a double, may be null or NaN), `n` (an integer,
may be null) and `s` (a string, may be null)."""
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.functions import coalesce, col, lit, when

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


#: every shape the lowering reads, run against Spark by the agreement test
READ = ("bands", "no_otherwise", "null_check", "negation_and_or", "membership",
        "arithmetic", "equality", "first_present", "by_attribute", "chained")
