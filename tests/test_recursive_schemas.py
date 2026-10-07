# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A schema that refers to itself is a language: a self-referential
dataclass, TypedDict or pydantic model, or a JSON Schema with a local
`$ref`, adapts without recursing forever. Members are acyclic; samples
are members by the ecosystem's own validator, nested values are the
real class, and draws stay within the bounds the schema states or,
where it states none, the sampling bounds (depth 8, nodes 256,
width 16) the language publishes; a value far deeper than the
recursion limit is checked, and a cycle is refused where it closes."""
import importlib.util
import random

import pytest

pytest.importorskip("mathema")

from mathema.conjecture import check_conjectures, claim  # noqa: E402

from mathema_language.schema import RowLanguage  # noqa: E402
from mathema_language.schema.adaptors import adapt_row  # noqa: E402
from mathema_language.schema.structure import record_measures  # noqa: E402
from mathema_language.vocabulary import tree  # noqa: E402
from tests import _recursive_shapes as shapes  # noqa: E402


def _shapes():
    out = [("dataclass", shapes.Node), ("typeddict", shapes.NodeDict)]
    if importlib.util.find_spec("jsonschema") is not None:
        out += [("jsonschema-root", shapes.NODE_SCHEMA), ("jsonschema-defs", shapes.TREE_SCHEMA)]
    try:
        from tests._recursive_pydantic import PNode
        out.append(("pydantic", PNode))
    except ImportError:
        pass
    return out


SHAPES = _shapes()


@pytest.fixture(params=SHAPES, ids=[n for n, _ in SHAPES])
def language(request):
    lang = adapt_row(request.param[1])
    assert isinstance(lang, RowLanguage), lang
    return lang


def test_a_recursive_schema_adapts_and_states_its_sampling_bounds(language):
    assert "ref" in repr(language.schema) or language.schema.definitions
    stated = language.to_json()["x-mathema"]["sampling"]
    assert set(stated) >= {"depth", "nodes", "width"}
    assert stated["depth"] <= 8 and stated["nodes"] <= 256


def test_samples_are_members_and_stay_within_the_sampling_bounds(language):
    rng = random.Random(1)
    depths = set()
    for _ in range(80):
        v = language.sample(rng)
        assert language.ecosystem.validate_row(language.schema, v) == [], v
        depth, nodes, _ = record_measures(language.schema, v)
        assert depth <= 8 and nodes <= 256, (depth, nodes)
        depths.add(depth)
    assert max(depths) >= 3, depths


def test_nested_values_are_the_real_class():
    lang = adapt_row(shapes.Node)
    rng = random.Random(4)
    for _ in range(40):
        v = lang.sample(rng)
        stack = [v]
        while stack:
            n = stack.pop()
            assert isinstance(n, shapes.Node), n
            stack.extend(n.children)


def test_a_schema_stated_bound_is_the_language_s():
    pytest.importorskip("pydantic")
    from tests._recursive_pydantic import PNode
    lang = adapt_row(PNode)
    rng = random.Random(2)
    for _ in range(60):
        assert tree.width(lang.sample(rng)) <= 3
    pytest.importorskip("jsonschema")
    lang = adapt_row(shapes.TREE_SCHEMA)
    for _ in range(60):
        assert tree.width(lang.sample(rng)["root"]) <= 3


def test_a_value_far_deeper_than_the_recursion_limit_is_checked():
    lang = adapt_row(shapes.Node)
    spine = shapes.Node(0)
    cur = spine
    for i in range(1, 3000):
        nxt = shapes.Node(i)
        cur.children.append(nxt)
        cur = nxt
    assert lang.contains(spine)
    cur.children.append(shapes.Node("not an int"))
    problems = lang.explain(spine)
    assert problems and problems[0].path.endswith(".children[0].value"), problems[0].path


def test_a_cycle_is_refused_where_it_closes():
    lang = adapt_row(shapes.Node)
    a = shapes.Node(1)
    b = shapes.Node(2, [a])
    a.children.append(b)
    assert not lang.contains(a)
    (problem,) = [p for p in lang.explain(a) if "acyclic" in p.predicate]
    assert problem.path == ".children[0].children[0]", problem.path


def test_optional_self_reference_adapts():
    lang = adapt_row(shapes.Pair)
    rng = random.Random(5)
    v = lang.sample(rng)
    assert isinstance(v, shapes.Pair) and lang.contains(v)


def test_a_claim_over_a_recursive_language_adjudicates():
    # bounded, so the recursive helpers stay inside the stack; the
    # unbounded language's deep spine is the structure-hazard tests' case
    bounded = "L[tests._recursive_shapes.Node, depth <= 20]"
    (p,) = check_conjectures(shapes.size, [claim(f"for t in {bounded}, f(t) >= 1")])
    assert p.verdict in ("holds", "proven"), (p.verdict, p.note, p.counterexample)
    (q,) = check_conjectures(shapes.height, [claim(
        f"let size = tests._recursive_shapes.size, for t in {bounded}, f(t) <= size(t)")])
    assert q.verdict in ("holds", "proven"), (q.verdict, q.note, q.counterexample)
    (r,) = check_conjectures(shapes.height, [claim(f"for t in {bounded}, f(t) <= 2")])
    assert r.verdict == "falsified", (r.verdict, r.note)


def test_a_depth_refinement_bounds_a_recursive_language():
    from mathema.domain import parse_binding

    from mathema_language._surface import resolve_language
    lang = resolve_language(parse_binding("t in L[tests._recursive_shapes.Node, depth <= 3]")[1].pieces[0])
    rng = random.Random(7)
    for _ in range(40):
        assert record_measures(lang.schema if hasattr(lang, "schema") else lang.base.schema,
                               lang.sample(rng))[0] <= 3
