# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The SQLAlchemy shapes the row-language tests run over."""
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
