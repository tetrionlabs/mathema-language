# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The table vocabulary over the plain reading: each function does
what its name says on mapping and attribute rows, `frame_eq`'s
policies flip its answer, every function carries its id, and one
binds into a claim over a frame language with `let`."""
import math
import sys
import types
from dataclasses import dataclass

import pytest

from mathema_language.vocabulary import table as t


@dataclass
class Row:
    id: int
    x: float


ROWS = [{"id": 1, "x": 1.0}, {"id": 2, "x": None}, {"id": 3, "x": math.nan}]
ATTRS = [Row(1, 1.0), Row(2, 2.0)]


def test_reads_over_mapping_and_attribute_rows():
    assert t.rows(ROWS) == 3 and t.rows(ATTRS) == 2
    assert t.columns(ROWS) == ("id", "x") and t.columns(ATTRS) == ("id", "x")
    assert t.nulls(ROWS, "x") == 2 and t.nulls(ATTRS, "x") == 0
    assert t.unique(ROWS, "id") and not t.unique(ROWS + [{"id": 1, "x": 0.0}], "id")
    assert t.sorted_by(ATTRS, "id") and not t.sorted_by(list(reversed(ATTRS)), "id")
    assert t.project(ATTRS, "x") == [{"x": 1.0}, {"x": 2.0}]
    assert sorted(r.id for r in t.permute(ATTRS, seed=1)) == [1, 2]
    assert t.sum_of(ROWS, "x") == 1.0 and t.sum_of(ATTRS, "x") == 3.0


def test_frame_eq_policies_flip_the_answer():
    a = [{"id": 1, "x": math.nan}, {"id": 2, "x": None}]
    b = [{"id": 2, "x": None}, {"id": 1, "x": math.nan}]
    assert not t.frame_eq(a, b)
    assert t.frame_eq(a, b, order=False)
    assert not t.frame_eq(a, b, order=False, nan="never")
    assert not t.frame_eq(a, b, order=False, null="never")
    assert t.frame_eq([{"x": 1.0}], [{"x": 1.05}], tolerance=0.1)
    assert not t.frame_eq([{"x": 1.0}], [{"x": 1.05}])
    assert t.frame_eq([{"x": 1.0, "y": 0}], [{"x": 1.0, "y": 9}], columns=["x"])
    assert not t.frame_eq(ATTRS, ATTRS[:1])


def test_every_function_carries_its_id():
    for name, fn in t.VOCABULARY.items():
        assert fn.__mathema_vocabulary__ == f"table.{name}@1"


def test_a_let_bound_table_function_adjudicates_over_a_frame_language():
    pytest.importorskip("mathema")
    from mathema.conjecture import check_conjectures, claim

    from mathema_language.schema._tables import frame_of

    module = types.ModuleType("vocab_frames")
    module.ORDERS = frame_of(Row, primary_key="id", row_count=(0, 5))

    def keep_positive(orders: list) -> list:
        """The rows whose x is positive, in order."""
        return [o for o in orders if o.x > 0]

    module.keep_positive = keep_positive
    sys.modules["vocab_frames"] = module
    try:
        (p,) = check_conjectures(keep_positive, [claim(
            "let n = mathema_language.vocabulary.table.rows, "
            "for orders in L[vocab_frames.ORDERS], n(f(orders)) <= n(orders)", route="probe")])
        assert p.verdict == "holds", (p.verdict, p.note, p.counterexample)
        (q,) = check_conjectures(keep_positive, [claim(
            "let u = mathema_language.vocabulary.table.unique, "
            "for orders in L[vocab_frames.ORDERS], u(f(orders), 'id') == True", route="probe")])
        assert q.verdict == "holds", (q.verdict, q.note, q.counterexample)
    finally:
        del sys.modules["vocab_frames"]
