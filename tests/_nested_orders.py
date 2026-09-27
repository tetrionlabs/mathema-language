# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Orders with a nested address and a list of lines, as dataclasses and
as TypedDicts, for the tests on nested records."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, TypedDict

from mathema_language.lexicon import Ge, Le, MaxLen


@dataclass
class Address:
    """Where an order ships: a postal code of up to five characters."""
    zip: Annotated[str, MaxLen(5)] | None = None


@dataclass
class OrderLine:
    """One line: a quantity from one to ten."""
    qty: Annotated[int, Ge(1), Le(10)]


@dataclass
class Order:
    """An order: where it ships and its lines."""
    address: Address
    lines: list[OrderLine] = field(default_factory=list)


def largest_qty(o: Order) -> int:
    """The largest quantity on any line, 0 for no lines."""
    return max((line.qty for line in o.lines), default=0)


def zip_width(o: Order) -> int:
    """The columns the postal code takes, 0 when there is none."""
    return len(o.address.zip) if o.address.zip is not None else 0


def has_zip(o: Order) -> bool:
    """Whether the order has a postal code."""
    return o.address.zip is not None


class AddressDict(TypedDict):
    """An address as a mapping."""
    zip: str


class OrderDict(TypedDict):
    """An order as a mapping, with its address as a mapping."""
    address: AddressDict
