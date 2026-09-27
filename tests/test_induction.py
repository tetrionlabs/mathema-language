# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Structural induction, the derive strategy a recursive row language
supplies: a fold against a constant, two folds related affinely, and
sum-folds related by an ordering are proven when the base case and the
step both go through and the language's depth bound keeps the recursion
under the stack; over an unbounded language the mathematics is settled
and the implementation is not; anything outside the class, or a base
case that fails, is never a proof and never a disproof."""
import pytest

pytest.importorskip("mathema")

from mathema_language.schema.adaptors import adapt_row  # noqa: E402
from tests import _recursive_shapes as shapes  # noqa: E402

FNS = {"size": shapes.size, "height": shapes.height, "double_size": shapes.double_size,
       "leaves_plus": shapes.leaves_plus, "weight_total": shapes.weight_total,
       "mirror": shapes.mirror}


def _derive(schema, lhs, relation, rhs, depth=20):
    lang = adapt_row(schema)
    refinements = {"depth": (0, depth)} if depth is not None else {}
    return lang.derive(param="t", lhs=lhs, relation=relation, rhs=rhs,
                       functions=FNS, refinements=refinements)


@pytest.mark.parametrize("lhs,relation,rhs", [
    ("size(t)", ">=", "1"),
    ("height(t)", ">=", "1"),
    ("double_size(t)", "==", "2 * size(t)"),
    ("leaves_plus(t)", ">=", "size(t)"),
    ("size(t)", "<=", "leaves_plus(t)"),
])
def test_a_fold_claim_is_proven_by_induction(lhs, relation, rhs):
    result = _derive(shapes.Node, lhs, relation, rhs)
    assert result.status == "proven", result.sketch
    assert result.meta["mathema.derive_route"] == "induction"
    assert "induction over children" in result.sketch


def test_a_field_s_lower_bound_enters_the_proof():
    result = _derive(shapes.Weighted, "weight_total(t)", ">=", "0")
    assert result.status == "proven", result.sketch


def test_an_unbounded_language_settles_the_mathematics_only():
    result = _derive(shapes.Node, "size(t)", ">=", "1", depth=None)
    assert result.status == "undecided", result.sketch
    assert "the mathematics holds" in result.sketch and "recursion" in result.sketch


def test_a_base_case_that_fails_is_no_proof_and_no_disproof():
    result = _derive(shapes.Node, "size(t)", ">=", "2")
    assert result.status == "unliftable" and "base case" in result.sketch, result.sketch


def test_mixed_aggregates_are_outside_the_class():
    result = _derive(shapes.Node, "size(t)", ">=", "height(t)")
    assert result.status == "unliftable", result.sketch


def test_a_structure_returning_function_is_outside_the_class():
    result = _derive(shapes.Node, "size(mirror(t))", "==", "size(t)")
    assert result.status == "unliftable", result.sketch


def test_a_flat_schema_supplies_no_strategy():
    from dataclasses import dataclass

    @dataclass
    class Flat:
        x: int

    assert adapt_row(Flat).derive(param="t", lhs="x", relation=">=", rhs="0",
                                  functions={}) is None


@pytest.mark.parametrize("lhs,relation,rhs", [
    ("size(t)", "<=", "1"),
    ("size(t)", ">", "1"),
    ("height(t)", "<=", "1"),
    ("height(t)", "==", "1"),
    ("double_size(t)", "==", "3 * size(t)"),
    ("leaves_plus(t)", "<=", "size(t)"),
    ("size(t)", "<", "leaves_plus(t)"),
    ("size(t)", "==", "height(t)"),
])
def test_a_false_claim_is_never_proven(lhs, relation, rhs):
    assert _derive(shapes.Node, lhs, relation, rhs).status != "proven"


def test_the_target_spelled_f_reads_as_the_fold_it_recurses_on():
    lang = adapt_row(shapes.Node)
    result = lang.derive(param="t", lhs="f(t)", relation=">=", rhs="1",
                         functions={"f": shapes.size}, refinements={"depth": (0, 20)})
    assert result.status == "proven", result.sketch
    helper = lang.derive(param="t", lhs="f(t)", relation="==", rhs="2 * size(t)",
                         functions={"f": shapes.double_size}, refinements={"depth": (0, 20)})
    assert helper.status == "proven", helper.sketch


def _claim(fn, text):
    from mathema.conjecture import check_conjectures, claim
    (p,) = check_conjectures(fn, [claim(text)])
    return p


def test_a_bounded_claim_is_proven_by_induction_end_to_end():
    p = _claim(shapes.size, "for t in L[tests._recursive_shapes.Node, depth <= 20], f(t) >= 1")
    assert (p.verdict, p.route) == ("proven", "derive:induction"), (p.verdict, p.route, p.note)
    p = _claim(shapes.double_size,
               "for t in L[tests._recursive_shapes.Node, depth <= 20], f(t) == 2 * size(t)")
    assert (p.verdict, p.route) == ("proven", "derive:induction"), (p.verdict, p.route, p.note)


def test_an_unbounded_claim_is_left_to_execution_which_finds_the_stack_limit():
    p = _claim(shapes.size, "for t in L[tests._recursive_shapes.Node], f(t) >= 1")
    assert p.verdict == "falsified" and "RecursionError" in p.counterexample, (p.verdict, p.note)


def test_a_false_claim_is_falsified_by_a_real_tree_end_to_end():
    p = _claim(shapes.size, "for t in L[tests._recursive_shapes.Node, depth <= 20], f(t) >= 2")
    assert p.verdict == "falsified" and not p.route.startswith("derive"), (p.verdict, p.route)
