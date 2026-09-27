# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The vocabulary a claim binds with `let`: the text operations of the
`mathema/language` dialect and the structure of nested values, each a
plain function carrying a neutral id
in `__mathema_vocabulary__` so another runtime can map it. The table
operations are internal and held with the table languages."""
from . import text, tree

__all__ = ["text", "tree"]
