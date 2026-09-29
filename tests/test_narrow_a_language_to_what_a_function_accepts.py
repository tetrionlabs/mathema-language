# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A claim over a language holding inputs the function refuses is
falsified: the language is too wide. `refused_inputs` shows what a
function refuses among a language's members, and `narrow_language`
returns the language without them, the specific language the claim
should quantify over. An input is refused when the call raises one of
the errors named (`ValueError` unless told otherwise); any other
exception is a crash and is never taken for a refusal."""
import random

import pytest
from mathema.conjecture import check_conjectures, claim
from mathema.languages import language_problems

from mathema_language.narrowing import refused_inputs
from mathema_language.text import UNICODE
from tests._narrowing_shapes import LABELS, TICKET_CODES, display_label, ticket_code


def test_refused_inputs_lists_what_the_function_refuses_and_why():
    refused = refused_inputs(display_label, UNICODE)
    values = [r.value for r in refused]
    assert "" in values and " " in values
    assert all(not v.strip() for v in values)
    assert {r.error for r in refused} == {"ValueError"}


def test_only_the_named_errors_are_refusals():
    from tests._narrowing_shapes import Refused
    with pytest.raises(Refused):
        refused_inputs(ticket_code, UNICODE)
    refused = refused_inputs(ticket_code, UNICODE, errors=(Refused,))
    assert "" in [r.value for r in refused]
    assert {r.error for r in refused} == {"Refused"}


def test_a_crash_is_never_taken_for_a_refusal():
    def crashes(s):
        return s[0]

    with pytest.raises(IndexError):
        refused_inputs(crashes, UNICODE)


def test_the_narrowed_language_is_the_base_without_the_refused_inputs():
    assert language_problems(LABELS) == []
    assert LABELS.contains("a") and LABELS.contains(" a ")
    assert not LABELS.contains(" ") and not LABELS.contains("")
    assert not LABELS.contains(5)
    (problem,) = LABELS.explain(" ")
    assert "display_label" in problem.predicate and "ValueError" in problem.predicate
    rng = random.Random(1)
    assert all(display_label(LABELS.sample(rng)) for _ in range(50))
    assert all(LABELS.contains(h.value) for h in LABELS.hazards())


def test_the_outside_draw_is_a_refused_input():
    rng = random.Random(2)
    outside = [LABELS.outside(rng) for _ in range(10)]
    assert any(isinstance(v, str) and not v.strip() for v in outside)
    assert not any(LABELS.contains(v) for v in outside)


def test_a_claim_over_the_wide_language_falsifies_and_over_the_narrowed_one_holds():
    (wide,) = check_conjectures(display_label, [claim(
        "for s in L[unicode], len(display_label(s)) >= 1")])
    assert wide.verdict == "falsified"
    (narrow,) = check_conjectures(display_label, [claim(
        "for s in L[tests._narrowing_shapes.LABELS], len(display_label(s)) >= 1")])
    assert narrow.verdict == "holds", narrow.note
    (refuses,) = check_conjectures(display_label, [claim(
        "for s in L[tests._narrowing_shapes.LABELS], excluded_outside_domain(s)")])
    assert refuses.verdict in ("holds", "proven"), (refuses.verdict, refuses.counterexample)


def test_a_library_s_own_refusal_narrows_when_named():
    assert TICKET_CODES.contains("a1") and not TICKET_CODES.contains("--")
    (p,) = check_conjectures(ticket_code, [claim(
        "for s in L[tests._narrowing_shapes.TICKET_CODES], len(ticket_code(s)) >= 1")])
    assert p.verdict == "holds", p.note
