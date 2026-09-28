# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The ecosystems: what a record is in one library, and that
library's own validation of it."""
from ._base import Ecosystem
from .plain import AttributeEcosystem, PlainEcosystem

__all__ = ["AttributeEcosystem", "Ecosystem", "PlainEcosystem"]
