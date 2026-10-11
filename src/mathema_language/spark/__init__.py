# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Spark code read as the row functions it computes, so a claim about a
column is a claim about a function of one row (`rule`)."""
from .lower import NotRead, rule

__all__ = ["NotRead", "rule"]
