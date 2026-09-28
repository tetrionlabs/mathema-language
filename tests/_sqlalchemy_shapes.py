# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The SQLAlchemy shapes the row-language tests run over."""
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

META = sa.MetaData()

ORDERS_TABLE = sa.Table(
    "orders", META,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("qty", sa.Integer, nullable=False),
    sa.Column("price", sa.Float, nullable=False),
    sa.Column("sku", sa.String(8), nullable=False),
    sa.Column("kind", sa.Enum("web", "shop", name="kind"), nullable=False),
    sa.Column("note", sa.String(80), nullable=True),
    sa.CheckConstraint("qty BETWEEN 1 AND 10", name="qty_range"),
    sa.CheckConstraint("price >= 0", name="price_nonneg"),
)


class Base(DeclarativeBase):
    pass


class Sku(Base):
    __tablename__ = "skus"
    code: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(20))


class Line(Base):
    __tablename__ = "lines"
    __table_args__ = (sa.CheckConstraint("qty > 0", name="qty_pos"),
                      sa.UniqueConstraint("sku", "batch", name="one_per_batch"))
    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[int] = mapped_column(sa.ForeignKey("skus.code"))
    batch: Mapped[int] = mapped_column(sa.Integer)
    qty: Mapped[int] = mapped_column(sa.Integer)


class Order(Base):
    """An order row whose CHECK constraints sit on the columns, the way
    `mapped_column(sa.CheckConstraint(...))` writes them."""
    __tablename__ = "orders_by_column"
    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(sa.String(12))
    quantity: Mapped[int] = mapped_column(sa.CheckConstraint("quantity BETWEEN 1 AND 100"))
    unit_price: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2),
                                                sa.CheckConstraint("unit_price >= 0"))


def order_total(order: Order) -> Decimal:
    """What the customer pays for the order."""
    return order.quantity * order.unit_price
