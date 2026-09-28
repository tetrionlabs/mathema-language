# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The SQLAlchemy adaptor passes the conformance checks, returns None
for anything that is not a `Table` or a mapped class, reads what it can
of the table into the neutral model, and leaves the rest to the
database: a CHECK constraint the neutral model cannot read is enforced
by inserting the record into an in-memory SQLite database. A mapped
class that is also a dataclass goes to this adaptor, not the dataclass
one."""
import pytest

sa = pytest.importorskip("sqlalchemy")

from mathema_language.conformance import (  # noqa: E402
    assert_row_adaptor,
    foreign_object_problems,
)
from mathema_language.schema.adaptors import adapt_row  # noqa: E402
from mathema_language.schema.adaptors.sqlalchemy import adapt  # noqa: E402
from tests import _sqlalchemy_shapes as shapes  # noqa: E402


@pytest.mark.parametrize("obj", [shapes.ORDERS_TABLE, shapes.Line], ids=["table", "mapped class"])
def test_passes_the_conformance_checks(obj):
    language = assert_row_adaptor(obj, adapt=adapt)
    assert type(language.ecosystem).__name__ == "SqlAlchemyEcosystem"


def test_returns_none_for_other_objects():
    assert foreign_object_problems(adapt) == []


def test_a_check_the_neutral_model_cannot_read_is_the_database_s():
    table = sa.Table("coded", sa.MetaData(),
                     sa.Column("id", sa.Integer, primary_key=True),
                     sa.Column("code", sa.String(8), nullable=False),
                     sa.CheckConstraint("length(code) >= 3", name="code_long_enough"))
    language = adapt(table)
    assert language.contains({"id": 1, "code": "abc"})
    assert [(p.path, p.predicate) for p in language.explain({"id": 1, "code": "ab"})] == [
        ("", "check code_long_enough")]


def test_a_mapped_dataclass_goes_to_this_adaptor():
    from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column

    class Base(MappedAsDataclass, DeclarativeBase):
        pass

    class Item(Base):
        __tablename__ = "items"
        __table_args__ = (sa.CheckConstraint("qty > 0", name="qty_pos"),)
        id: Mapped[int] = mapped_column(primary_key=True)
        qty: Mapped[int] = mapped_column(sa.Integer)

    import dataclasses
    assert dataclasses.is_dataclass(Item)
    assert type(adapt_row(Item).ecosystem).__name__ == "SqlAlchemyEcosystem"


def _lift_verdict(fn, law):
    from mathema.conjecture import check_conjectures, claim
    (p,) = check_conjectures(fn, [claim(law)])
    assert "UNCORROBORATED" not in (p.note or ""), p.note
    return p.verdict


def total(row) -> float:
    """Quantity times price."""
    return row["qty"] * row["price"]


def width(row) -> int:
    """The columns the sku takes, with a space either side."""
    return len(row["sku"]) + 2


def test_the_lift_reads_the_fields_through_this_adaptor():
    assert _lift_verdict(total, "for row in L[tests._sqlalchemy_shapes.ORDERS_TABLE], f(row) >= 0") == "proven"
    assert _lift_verdict(width, "for row in L[tests._sqlalchemy_shapes.ORDERS_TABLE], f(row) <= 10") == "proven"
    assert _lift_verdict(width, "for row in L[tests._sqlalchemy_shapes.ORDERS_TABLE], f(row) <= 9") == "falsified"


def test_a_column_s_own_check_constraints_are_read():
    fields = {f.name: f.constraints for f in adapt_row(shapes.Order).schema.fields}
    assert (fields["quantity"].min, fields["quantity"].max) == (1, 100)
    assert fields["unit_price"].min == 0


def test_a_claim_over_column_checks_is_decided():
    pytest.importorskip("mathema")
    from mathema.conjecture import check_conjectures, claim
    (p,) = check_conjectures(shapes.order_total, [claim(
        "for order in L[tests._sqlalchemy_shapes.Order], f(order) >= 0")])
    assert p.verdict in ("proven", "holds"), (p.verdict, p.note)
