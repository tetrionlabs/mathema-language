# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Each tree word means one thing. On a record tree `depth`, `nodes`,
`width` and `leaves` count records, whether written as a refinement key
(`L[Node, width <= 3]`) or called from the tree vocabulary; on a plain
nested dict or list, which has no schema to say what a record is, the
vocabulary counts every container and value. `children` is no longer a
key: the widest fan-out is `width`."""
import pytest

pytest.importorskip("mathema")

from mathema.domain import parse_binding  # noqa: E402
from mathema.languages import UnknownRefinement, resolve_language  # noqa: E402

from mathema_language.vocabulary import tree  # noqa: E402
from tests import _recursive_shapes as shapes  # noqa: E402

THREAD = shapes.Node(1, [shapes.Node(2, [shapes.Node(3)]), shapes.Node(4)])


def test_on_a_record_tree_the_vocabulary_counts_records():
    assert (tree.depth(THREAD), tree.nodes(THREAD), tree.width(THREAD), tree.leaves(THREAD)) \
        == (3, 4, 2, 2)
    assert (tree.depth(shapes.Node(0)), tree.nodes(shapes.Node(0))) == (1, 1)


def test_on_plain_nested_values_it_counts_containers_and_values():
    assert (tree.depth([[[]]]), tree.nodes({"a": 0, "b": 0}), tree.width([0, 0, 0])) == (3, 3, 3)


def test_width_is_the_refinement_key_and_children_is_not():
    language = resolve_language(parse_binding("t in L[tests._recursive_shapes.Node, width <= 2]")[1].pieces[0])
    assert language.contains(THREAD)
    assert not language.contains(shapes.Node(0, [shapes.Node(1)] * 3))
    with pytest.raises(UnknownRefinement):
        resolve_language(parse_binding("t in L[tests._recursive_shapes.Node, children <= 2]")[1].pieces[0])


def test_the_record_states_width_in_its_sampling_bounds():
    from mathema_language.schema.adaptors import adapt_row
    assert set(adapt_row(shapes.Node).sampling) >= {"depth", "nodes", "width"}
