# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The shop's stock-keeping units as a language of their own: three
capital letters, a hyphen and four digits, `ABC-1234`."""
import re

from mathema_language.text import TextLanguage

SKU = TextLanguage(
    "sku", level="predicate",
    accepts=lambda s: re.fullmatch(r"[A-Z]{3}-[0-9]{4}", s) is not None,
    generate=lambda rng: "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(3))
    + "-" + "".join(rng.choice("0123456789") for _ in range(4)),
    outside_pool="a-_ ")


def parse_sku(text: str) -> tuple:
    """A SKU split into its product line and item number."""
    line, number = text.split("-")
    return line, int(number)


def format_sku(parts: tuple) -> str:
    """A product line and item number written as a SKU."""
    line, number = parts
    return f"{line}-{number:04d}"


def normalise_sku(text: str) -> str:
    """A SKU typed by a person, as the stock system stores it."""
    return text.strip().upper()
