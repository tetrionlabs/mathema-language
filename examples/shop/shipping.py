# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Parcels and their postage, as a dataclass."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from annotated_types import Ge, Le, MaxLen


@dataclass
class Parcel:
    postcode: Annotated[str, MaxLen(8)]
    weight_kg: Annotated[float, Ge(0.0), Le(30.0)]


def postage(parcel: Parcel) -> float:
    """What it costs to send the parcel: a base rate plus a rate per kilo."""
    return 3.5 + 1.2 * parcel.weight_kg


def address_label(parcel: Parcel) -> str:
    """The postcode printed on the parcel's label."""
    return parcel.postcode.upper()
