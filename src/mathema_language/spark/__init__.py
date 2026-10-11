# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Spark code read as the row functions it computes, so a claim about a
column is a claim about a function of the columns it reads (`rule`),
and what a rule does at each hole of its inputs (`holes`)."""
from .holes import HoleOutcome, holes
from .lower import NotRead, rule

__all__ = ["HoleOutcome", "NotRead", "holes", "rule"]
