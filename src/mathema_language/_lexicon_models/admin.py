# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""An admin command line with two subcommands, and a restock tool with
none."""
from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    """`shop restock SKU [--quantity N]` and `shop discount --percent P`."""
    parser = argparse.ArgumentParser(prog="shop")
    commands = parser.add_subparsers(dest="command", required=True)
    restock = commands.add_parser("restock")
    restock.add_argument("sku")
    restock.add_argument("--quantity", type=int, default=1)
    discount = commands.add_parser("discount")
    discount.add_argument("--percent", type=int, required=True)
    return parser


def build_restock_parser() -> argparse.ArgumentParser:
    """`restock SKU [--quantity N]`, a command line with no subcommands."""
    parser = argparse.ArgumentParser(prog="restock")
    parser.add_argument("sku")
    parser.add_argument("--quantity", type=int, default=1)
    return parser
