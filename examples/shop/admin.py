# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The shop's admin command line."""
import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    """`shop restock SKU [--quantity N]`, `shop discount --percent P`
    and `shop export [--to PATH]`."""
    parser = argparse.ArgumentParser(prog="shop")
    parser.add_argument("--verbose", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    restock = commands.add_parser("restock")
    restock.add_argument("sku")
    restock.add_argument("--quantity", type=int, default=1)
    discount = commands.add_parser("discount")
    discount.add_argument("--percent", type=int, required=True)
    export = commands.add_parser("export")
    export.add_argument("--to", type=Path, default=Path("orders.csv"))
    return parser


def units_ordered(args: argparse.Namespace) -> int:
    """How many units a command orders from the supplier, in cases of 12."""
    if args.command == "restock":
        return args.quantity * 12
    return 0


def discounted(args: argparse.Namespace, price: float) -> float:
    """A price after the discount command's percentage."""
    if args.command == "discount":
        return price * (100 - args.percent) / 100
    return price
