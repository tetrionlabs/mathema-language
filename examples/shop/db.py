# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The shop's orders table, as a SQLAlchemy mapped class."""
from __future__ import annotations

from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(sa.String(12))
    quantity: Mapped[int] = mapped_column(sa.CheckConstraint("quantity BETWEEN 1 AND 100"))
    unit_price: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2),
                                                sa.CheckConstraint("unit_price >= 0"))


def order_total(order: Order) -> Decimal:
    """What the customer pays for the order."""
    return order.quantity * order.unit_price
