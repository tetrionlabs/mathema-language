# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Budgets for the seeded property tests. Each runs at a small budget by
default; its full size is a test marked `heavy` that runs only with the
environment flag `MATHEMA_LANGUAGE_HEAVY=1`, selected with `-m heavy`.
Every test prints its seed and how many cases it checked."""
import os

import pytest

#: whether the full-size runs are asked for
HEAVY = os.environ.get("MATHEMA_LANGUAGE_HEAVY") == "1"

def heavy(test):
    """Mark a full-size run: selected by `-m heavy`, and skipped without the flag."""
    skip = pytest.mark.skipif(not HEAVY, reason="the full budget runs with MATHEMA_LANGUAGE_HEAVY=1")
    return pytest.mark.heavy(skip(test))


def report(name: str, seed: int, **counts: int) -> None:
    """Print what a property test checked, for the log of the run."""
    print(f"{name}: seed {seed}, " + ", ".join(f"{k} {v}" for k, v in counts.items()))
