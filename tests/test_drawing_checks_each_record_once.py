# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Drawing a recursive record checks each record a bounded number of
times, not once per enclosing level, so a draw costs time linear in
the records it builds; the finished member is still validated whole."""
import random

from mathema_language.schema import checks
from mathema_language.schema.adaptors import adapt_row
from mathema_language.schema.structure import record_measures
from tests import _recursive_shapes as shapes


def test_record_checks_per_draw_are_linear_in_its_records(monkeypatch):
    lang = adapt_row(shapes.Node)
    calls = []
    original = checks._Walker._row

    def counted(self, *args):
        calls.append(1)
        return original(self, *args)

    monkeypatch.setattr(checks._Walker, "_row", counted)
    rng = random.Random(3)
    worst = 0.0
    for _ in range(30):
        calls.clear()
        member = lang.sample(rng)
        records = record_measures(lang.schema, member)[1]
        worst = max(worst, len(calls) / records)
    assert worst <= 4, worst


def test_a_nested_record_that_breaks_its_schema_is_still_refused():
    lang = adapt_row(shapes.Node)
    bad = shapes.Node(1, [shapes.Node("not an int")])
    assert not lang.contains(bad)
    assert [p.path for p in lang.explain(bad)] == [".children[0].value"]
