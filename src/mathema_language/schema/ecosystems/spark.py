# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Spark records as dicts, shaped like `Row.asDict(recursive=True)`, and
validated by the neutral checker: the schema's types, widths, decimal
precision and nullability as this package reads them, not as a running
Spark session would convert a value."""
from __future__ import annotations

from .plain import PlainEcosystem


class SparkEcosystem(PlainEcosystem):
    """Records are mappings of a Spark struct's fields."""

    name = "spark"


__all__ = ["SparkEcosystem"]
