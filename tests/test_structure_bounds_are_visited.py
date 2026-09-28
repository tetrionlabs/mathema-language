# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A structure refinement on a recursive row language visits its
bounds: the member at each bound, or nearest inside it where no member
has exactly that measure, is a hazard, the base
member nearest past the bound is the outside draw, and random draws climb the depth ladder
however many times the language is resolved, so a claim false only on
deep or wide members is falsified."""
import random

import pytest

pytest.importorskip("mathema")

from mathema.conjecture import check_conjectures, claim  # noqa: E402
from mathema.domain import parse_binding  # noqa: E402
from mathema.languages import resolve_language  # noqa: E402

from mathema_language.schema.structure import record_measures  # noqa: E402
from tests import _recursive_shapes as shapes  # noqa: E402

NODE = "tests._recursive_shapes.Node"


def _measure(key):
    schema = _language(f"L[{NODE}]").schema
    return lambda v: record_measures(schema, v)[("depth", "nodes", "width").index(key)]


def depth(v):
    return _measure("depth")(v)


def _language(text):
    return resolve_language(parse_binding(f"t in {text}")[1].pieces[0])


@pytest.mark.parametrize("key,bound", [("depth", 3), ("depth", 9), ("width", 4),
                                       ("nodes", 12)])
def test_the_member_at_the_bound_is_a_hazard_and_one_past_is_outside(key, bound):
    lang = _language(f"L[{NODE}, {key} <= {bound}]")
    measure = _measure(key)
    reached = max(measure(h.value) for h in lang.hazards())
    assert reached == bound, reached
    outside = lang.outside(random.Random(0))
    assert outside is not None and measure(outside) == bound + 1, outside
    assert _language(f"L[{NODE}]").contains(outside)


def test_draws_climb_the_ladder_when_every_draw_resolves_afresh():
    rng = random.Random(1)
    depths = {depth(_language(f"L[{NODE}]").sample(rng)) for _ in range(60)}
    assert max(depths) >= 4, sorted(depths)


@pytest.mark.parametrize("fn,text", [
    (shapes.widest, f"for t in L[{NODE}, depth <= 8, width <= 4], f(t) <= 3"),
    (shapes.height, f"for t in L[{NODE}, depth <= 4], f(t) <= 3"),
    (shapes.size, f"for t in L[{NODE}, nodes <= 30], f(t) <= 4"),
])
def test_a_claim_false_only_at_the_bound_is_falsified(fn, text):
    (p,) = check_conjectures(fn, [claim(text)])
    assert p.verdict == "falsified", (p.verdict, p.note)
