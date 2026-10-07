# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The signup form and the basket, as pydantic models."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SignupForm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=32)
    age: int = Field(ge=13, le=120)


def years_until_eighteen(form: SignupForm) -> int:
    """How many years until the user turns 18.

    Claims:
        at_most_five_years: for form in L[shop.forms.SignupForm], 0 <= years_until_eighteen(form) <= 5
    """
    return max(0, 18 - form.age)


class CartItem(BaseModel):
    sku: str
    quantity: int = Field(ge=1, le=10)


class Cart(BaseModel):
    items: list[CartItem]


def largest_quantity(cart: Cart) -> int:
    """The largest quantity of any one item, 0 for an empty cart."""
    return max((item.quantity for item in cart.items), default=0)


def welcome_message(form: SignupForm) -> str:
    """The first line of the welcome email."""
    return f"Welcome, {form.username}!"


class Checkout(BaseModel):
    cart: Cart
    postcode: str | None = Field(default=None, max_length=8)


def needs_postcode(checkout: Checkout) -> bool:
    """Whether the checkout page still has to ask for a postcode."""
    return checkout.postcode is None


def first_quantity(checkout: Checkout) -> int:
    """The quantity of the first item, 0 for an empty basket."""
    items = checkout.cart.items
    return items[0].quantity if items else 0
