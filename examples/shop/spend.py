# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Spend banding in the procurement pipeline, as Spark code."""
from pyspark.sql import DataFrame
from pyspark.sql.functions import col, lit, when

STRATEGIC_FROM = 10000


def classify_po_category(df: DataFrame, value_col: str = "po_value") -> DataFrame:
    """Each purchase order's spend band: Invalid for no value or a
    negative one, then Micro, Standard, Strategic and Major."""
    return df.withColumn(
        "po_category",
        when(col(value_col).isNull() | (col(value_col) < 0), lit("Invalid"))
        .when(col(value_col) < 1000, lit("Micro"))
        .when(col(value_col) < STRATEGIC_FROM, lit("Standard"))
        .when(col(value_col) < 50000, lit("Strategic"))
        .otherwise(lit("Major")),
    )


def classify_po_category_bug(df: DataFrame, value_col: str = "po_value") -> DataFrame:
    """The same banding with the Standard band's edge written <=."""
    return df.withColumn(
        "po_category",
        when(col(value_col).isNull() | (col(value_col) < 0), lit("Invalid"))
        .when(col(value_col) < 1000, lit("Micro"))
        .when(col(value_col) <= STRATEGIC_FROM, lit("Standard"))
        .when(col(value_col) < 50000, lit("Strategic"))
        .otherwise(lit("Major")),
    )


def classify_po_category_unguarded(df: DataFrame, value_col: str = "po_value") -> DataFrame:
    """The same banding with no test for a missing value."""
    return df.withColumn(
        "po_category",
        when(col(value_col) < 0, lit("Invalid"))
        .when(col(value_col) < 1000, lit("Micro"))
        .when(col(value_col) < STRATEGIC_FROM, lit("Standard"))
        .when(col(value_col) < 50000, lit("Strategic"))
        .otherwise(lit("Major")),
    )
