# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The text hazards include a digit `str.isdigit` accepts but `int`
refuses, the input behind a common guarded-parse bug."""
import pytest

pytest.importorskip("mathema")

from mathema.conjecture import check_conjectures, claim  # noqa: E402

from tests import _text_bugs as bugs  # noqa: E402


def test_a_digit_int_refuses_falsifies_a_guarded_parse():
    (p,) = check_conjectures(bugs.parse_quantity, [claim(
        "for text in L[unicode], f(text) >= 0")])
    assert p.verdict == "falsified" and "'²'" in p.counterexample, (p.verdict, p.counterexample)
