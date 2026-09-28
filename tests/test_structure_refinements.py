# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""`depth`, `nodes` and `width` refine a language of nested values:
`L[json, depth <= 3]` is the JSON documents nested at most three
levels. The measures are `vocabulary.tree`'s, taken iteratively so a
document far deeper than the recursion limit is measured; members,
samples and hazards stay inside the bound, the plain member at each
bound is the simplest document of that measure, the member one past it
is the outside draw, and a language of plain text refuses the keys."""
import json
import random
from dataclasses import dataclass

import pytest

pytest.importorskip("mathema")

from mathema.conjecture import check_conjectures, claim  # noqa: E402
from mathema.domain import parse_binding  # noqa: E402

from mathema_language._surface import refinement_keys, resolve_language  # noqa: E402
from mathema_language.text.json_structure import scan  # noqa: E402
from mathema_language.vocabulary import tree  # noqa: E402


def _language(text):
    return resolve_language(parse_binding(f"s in {text}")[1].pieces[0])


def test_the_tree_measures():
    assert (tree.depth(0), tree.nodes(0), tree.width(0), tree.leaves(0)) == (0, 1, 0, 1)
    assert (tree.depth([]), tree.nodes([]), tree.width([]), tree.leaves([])) == (1, 1, 0, 1)
    assert tree.depth([[1]]) == 2 and tree.nodes([[1]]) == 3
    doc = {"a": [1, 2, {"b": None}], "c": "x"}
    assert tree.depth(doc) == 3 and tree.nodes(doc) == 7
    assert tree.width(doc) == 3 and tree.leaves(doc) == 4

    @dataclass
    class Address:
        city: str

    @dataclass
    class Person:
        name: str
        home: Address

    # a record tree is counted in records: a person and the address it holds
    assert tree.depth(Person("a", Address("b"))) == 2
    assert tree.nodes(Person("a", Address("b"))) == 2


def test_the_measures_are_iterative_and_refuse_a_cycle():
    deep = []
    for _ in range(5000):
        deep = [deep]
    assert tree.depth(deep) == 5001
    loop: list = []
    loop.append(loop)
    with pytest.raises(ValueError, match="contains itself"):
        tree.depth(loop)


def test_the_text_scan_agrees_with_the_parsed_value():
    rng = random.Random(3)
    lang = _language("L[json]")
    for _ in range(200):
        text = lang.sample(rng)
        value = json.loads(text)
        assert scan(text) == (tree.depth(value), tree.nodes(value),
                              tree.width(value), tree.leaves(value)), text
    for text in ('{"a": {"b": [1, "x,y", {"c": "]"}]}, "d": true}', '"s"', "[]", "{}",
                 '[{"k": "v\\\\"}, -1.5e3, null]'):
        value = json.loads(text)
        assert scan(text) == (tree.depth(value), tree.nodes(value),
                              tree.width(value), tree.leaves(value)), text
    assert scan("[" * 5000 + "]" * 5000)[0] == 5000


def test_the_keys_are_registered_by_the_package():
    assert {"depth", "nodes", "width"} <= set(refinement_keys())


@pytest.mark.parametrize("text,key,lo,hi", [
    ("L[json, depth <= 3]", "depth", 0, 3),
    ("L[json, depth in [2, 4]]", "depth", 2, 4),
    ("L[json, nodes <= 6]", "nodes", 1, 6),
    ("L[json, width <= 2]", "width", 0, 2),
])
def test_samples_and_hazards_stay_inside_and_the_outside_draw_does_not(text, key, lo, hi):
    lang = _language(text)
    measure = {"depth": 0, "nodes": 1, "width": 2}[key]
    rng = random.Random(0)
    for _ in range(100):
        s = lang.sample(rng)
        assert lo <= scan(s)[measure] <= hi, s
    measured = {scan(h.value)[measure] for h in lang.hazards()}
    assert hi in measured, measured
    outside = lang.outside(rng)
    assert outside is not None and not lang.contains(outside)


def test_the_plain_member_at_the_bound_is_the_simplest():
    lang = _language("L[json, depth <= 3]")
    first = lang.hazards()[0].value
    assert first in ("0", "[[[]]]"), first
    assert "[[[]]]" in [h.value for h in lang.hazards()]
    (problem,) = lang.explain("[[[[]]]]")
    assert problem.predicate == "depth <= 3"


def test_plain_text_refuses_a_structure_key():
    with pytest.raises(Exception, match="plain text"):
        _language("L[unicode, depth <= 3]")


def test_a_claim_over_bounded_json_adjudicates():
    import importlib.util
    import pathlib
    import sys
    import tempfile
    import textwrap
    p = pathlib.Path(tempfile.mkdtemp()) / "structure_fns.py"
    p.write_text(textwrap.dedent('''
        import json

        def canonical(doc: str) -> str:
            """The document with sorted keys and no spaces."""
            return json.dumps(json.loads(doc), sort_keys=True, separators=(",", ":"))

        def wrap(doc: str) -> str:
            """The document inside a list."""
            return "[" + doc + "]"
    '''))
    spec = importlib.util.spec_from_file_location("structure_fns", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["structure_fns"] = mod
    spec.loader.exec_module(mod)
    (holds,) = check_conjectures(mod.canonical, [claim(
        "for doc in L[json, depth <= 4], f(f(doc)) == f(doc)")])
    assert holds.verdict == "holds", (holds.verdict, holds.note, holds.counterexample)
    (closure,) = check_conjectures(mod.wrap, [claim(
        "for doc in L[json, depth <= 4], f(doc) in L[json, depth <= 4]")])
    assert closure.verdict == "falsified", (closure.verdict, closure.note)
    assert "[[[[[]]]]]" in closure.counterexample or "depth <= 4" in closure.counterexample, closure.counterexample
