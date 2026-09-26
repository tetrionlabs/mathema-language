# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The ecosystems: what a record and a table are in one library, and
that library's own validation of them."""
from ._base import Ecosystem
from .plain import AttributeEcosystem, PlainEcosystem

__all__ = ["AttributeEcosystem", "Ecosystem", "PlainEcosystem"]
