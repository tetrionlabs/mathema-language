# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A recursive language's hazards and shrinking work on its structure.
The hazards are the deepest member within the sampling bounds, the
widest node the schema allows, and a spine past the interpreter's
recursion limit (or, where the ecosystem's own validator stops sooner,
a spine at that limit, which the language states); shrinking hoists a
subtree into the root's place and drops list elements before touching
leaves, staying inside the language; draws climb a depth ladder instead
of clustering shallow."""
import random
import sys

import pytest

pytest.importorskip("mathema")

from mathema.conjecture import check_conjectures, claim  # noqa: E402

from mathema_language.schema.adaptors import adapt_row  # noqa: E402
from mathema_language.schema.structure import record_measures  # noqa: E402
from mathema_language.vocabulary import tree  # noqa: E402
from tests import _recursive_shapes as shapes  # noqa: E402


def _depth(lang, value):
    return record_measures(lang.schema, value)[0]


def _notes(lang):
    return {h.note: h.value for h in lang.hazards()}


def test_the_deepest_and_widest_members_are_hazards():
    lang = adapt_row(shapes.Node)
    hazards = lang.hazards()
    depths = [_depth(lang, h.value) for h in hazards]
    widths = [record_measures(lang.schema, h.value)[2] for h in hazards]
    assert lang.sampling["depth"] in depths, depths
    assert lang.sampling["children"] in widths, widths
    for h in hazards:
        assert lang.contains(h.value), h.note


def test_a_spine_past_the_recursion_limit_is_a_hazard():
    lang = adapt_row(shapes.Node)
    deepest = max(_depth(lang, h.value) for h in lang.hazards())
    assert deepest > sys.getrecursionlimit(), deepest


def test_the_ecosystem_s_own_depth_limit_is_found_and_stated():
    # the jsonschema validator recurses in Python, so it stops well
    # before a document's own nesting ends: that limit is part of what a
    # member is, found while the hazards are built and stated
    pytest.importorskip("jsonschema")
    lang = adapt_row(shapes.NODE_SCHEMA)
    limit = lang.to_json()["x-mathema"]["validator_depth_limit"]
    assert isinstance(limit, int) and 1 < limit < 5000
    for h in lang.hazards():
        assert lang.contains(h.value), h.note
    assert max(_depth(lang, h.value) for h in lang.hazards()) == limit


def test_pydantic_states_no_limit_where_it_has_none():
    pytest.importorskip("pydantic")
    from tests._recursive_pydantic import PNode
    lang = adapt_row(PNode)
    assert "validator_depth_limit" not in lang.to_json()["x-mathema"]
    assert max(_depth(lang, h.value) for h in lang.hazards()) > sys.getrecursionlimit()


def test_shrinking_hoists_a_subtree_and_drops_elements_inside_the_language():
    lang = adapt_row(shapes.Node)
    leaf = shapes.Node(3)
    mid = shapes.Node(2, [leaf, shapes.Node(4)])
    root = shapes.Node(1, [mid, shapes.Node(5)])
    candidates = list(lang.shrink(root))
    assert mid in candidates, "the subtree is hoisted into the root's place"
    assert any(isinstance(c, shapes.Node) and len(c.children) == 1 and c.value == 1
               for c in candidates), "one child dropped"
    assert all(lang.contains(c) for c in candidates)
    assert all(tree.nodes(c) < tree.nodes(root) for c in candidates[:3])


def test_draws_climb_a_depth_ladder():
    lang = adapt_row(shapes.Node)
    rng = random.Random(9)
    depths = {_depth(lang, lang.sample(rng)) for _ in range(64)}
    assert min(depths) <= 2 and max(depths) >= lang.sampling["depth"] - 1, sorted(depths)
    assert lang.to_json()["x-mathema"]["sampling"]["ladder"][0] == 1


def test_a_recursive_function_crashes_on_the_deep_spine_and_the_record_says_why():
    (p,) = check_conjectures(shapes.size, [claim("for t in L[tests._recursive_shapes.Node], f(t) >= 1")])
    assert p.verdict == "falsified", (p.verdict, p.note)
    assert "RecursionError" in p.counterexample, p.counterexample
    (q,) = check_conjectures(shapes.size, [claim(
        "for t in L[tests._recursive_shapes.Node, depth <= 20], f(t) >= 1")])
    assert (q.verdict, q.route) == ("proven", "derive:induction"), (q.verdict, q.note)
