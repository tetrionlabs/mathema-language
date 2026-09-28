# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The tree vocabulary by its short path, for claims:
`let depth = mathema_language.tree.depth, for t in L[...], depth(t) <= 6`.
`depth`, `nodes`, `width` and `leaves` count records on a record tree and
containers and values on any other nest; see
`mathema_language.vocabulary.tree`."""
from .vocabulary.tree import depth, leaves, nodes, width

__all__ = ["depth", "leaves", "nodes", "width"]
