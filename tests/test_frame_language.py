# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Internal and held, not part of the 0.1 surface. A frame language: every generated table is a member by the
ecosystem's own validator (keys distinct, count in range, every row a
member), the hazards are members, `outside` is not and says where,
shrinking stays inside, and `frame_of` bound to a module-level name
resolves in a claim as a dotted object."""
import random
import sys
import types
from dataclasses import dataclass
from typing import Annotated, Literal

import pytest

from mathema_language.schema._tables import FrameLanguage, frame_of

pytest.importorskip("mathema")
from mathema.conjecture import check_conjectures, claim  # noqa: E402
from mathema.languages import language_problems  # noqa: E402


class Ge:
    def __init__(self, ge):
        self.ge = ge


class Le:
    def __init__(self, le):
        self.le = le


@dataclass
class Order:
    id: int
    qty: Annotated[int, Ge(1), Le(10)]
    price: Annotated[float, Ge(0.0), Le(100.0)]
    kind: Literal["web", "shop"]
    note: str | None = None


ORDERS = frame_of(Order, primary_key="id", row_count=(1, 6))


def test_the_language_passes_the_conformance_checks():
    assert language_problems(ORDERS) == []
    assert ORDERS.kind == "table" and ORDERS.level == "schema"
    assert ORDERS.name == "Order_frame" and ORDERS.fields() is None
    assert ORDERS.to_json()["x-mathema"] == {"primary_key": ["id"]}


def test_every_generated_frame_is_a_member_by_the_ecosystem_s_own_validator():
    rng = random.Random(5)
    counts = set()
    for _ in range(100):
        frame = ORDERS.sample(rng)
        assert ORDERS.ecosystem._validate_frame(ORDERS.table, frame) == [], frame
        counts.add(len(frame))
        assert len({row.id for row in frame}) == len(frame)
    assert counts >= {1, 6}


def test_the_hazards_are_members_and_cover_the_shapes():
    hazards = ORDERS.hazards()
    notes = [h.note for h in hazards]
    assert "one row" in notes and "the most rows, 6" in notes
    assert "note: null in every row" in notes
    assert any(n.startswith("[0].qty:") for n in notes)
    for h in hazards:
        assert ORDERS.contains(h.value), (h.note, ORDERS.explain(h.value))
    assert "no rows" not in notes, "the count starts at one, so the empty table is outside"


def test_outside_is_never_a_member_and_says_where():
    rng = random.Random(9)
    paths = set()
    for _ in range(60):
        bad = ORDERS.outside(rng)
        assert bad is not None
        problems = ORDERS.explain(bad)
        assert problems, bad
        paths.update(p.path for p in problems)
    assert "key(id)" in paths and "rows" in paths
    assert any(p.startswith("[0].") for p in paths)


def test_shrinking_drops_rows_and_simplifies_cells_inside_the_language():
    rng = random.Random(2)
    frame = ORDERS.sample(rng)
    while len(frame) < 3:
        frame = ORDERS.sample(rng)
    smaller = list(ORDERS.shrink(frame))
    assert smaller and all(ORDERS.contains(s) for s in smaller)
    assert any(len(s) == len(frame) - 1 for s in smaller)


def test_frame_of_bound_to_a_module_name_resolves_in_a_claim():
    module = types.ModuleType("orders_schemas")
    module.ORDERS = ORDERS

    def revenue(orders: list) -> float:
        """The total of quantity times price."""
        return sum(o.qty * o.price for o in orders)

    module.revenue = revenue
    sys.modules["orders_schemas"] = module
    try:
        (p,) = check_conjectures(revenue, [claim(
            "for orders in L[orders_schemas.ORDERS], f(orders) >= 0", route="probe")])
        assert p.verdict == "holds", (p.verdict, p.note, p.counterexample)
        assert p.grammar == "mathema/language"
        described = p.meta["mathema.language"]["orders"][0]
        assert described["source"] == "object" and described["kind"] == "table"
        (q,) = check_conjectures(revenue, [claim(
            "for orders in L[orders_schemas.ORDERS], f(orders) <= 100", route="probe")])
        assert q.verdict == "falsified", (q.verdict, q.note)
    finally:
        del sys.modules["orders_schemas"]


def test_a_frame_with_a_parent_draws_its_foreign_keys_from_the_parent():
    from mathema_language.schema.model import ForeignKey

    @dataclass
    class Sku:
        code: int
        name: str

    @dataclass
    class Line:
        id: int
        sku: int

    lines = frame_of(Line, primary_key="id", row_count=(1, 4),
                     foreign_keys=(ForeignKey(("sku",), "Sku", ("code",)),),
                     parents={"Sku": Sku})
    assert isinstance(lines, FrameLanguage)
    frame = lines.sample(random.Random(1))
    assert lines.contains(frame)
    parent_rows = [Sku(code=row.sku, name="x") for row in frame]
    assert lines.ecosystem._validate_frame(lines.table, frame, {"Sku": parent_rows}) == []
    orphan = lines.ecosystem._validate_frame(lines.table, frame, {"Sku": []})
    assert orphan and orphan[0].path == "fk(sku)->Sku"
