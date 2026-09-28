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


def test_json_nested_past_the_recursion_limit_is_tried():
    import sys

    from mathema.languages import resolve_language

    from mathema_language.text.json_structure import scan
    language = resolve_language("json")
    deepest = max(scan(h.value)[0] for h in language.hazards() if language.contains(h.value))
    assert deepest > sys.getrecursionlimit(), deepest
    (p,) = check_conjectures(bugs.json_keys, [claim("for text in L[json], f(text) >= 0")])
    assert p.verdict == "falsified" and "RecursionError" in p.counterexample, (p.verdict, p.note)


def test_a_json_bound_on_nodes_or_width_tries_an_object_at_the_bound():
    (p,) = check_conjectures(bugs.json_keys, [claim("for text in L[json, nodes <= 20], f(text) <= 9")])
    assert p.verdict == "falsified", (p.verdict, p.note)
    (q,) = check_conjectures(bugs.json_keys, [claim("for text in L[json, width <= 12], f(text) <= 5")])
    assert q.verdict == "falsified", (q.verdict, q.note)
