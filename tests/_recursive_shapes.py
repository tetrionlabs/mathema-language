# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Self-referential schemas the recursive-schema tests run over, at
module level so their forward references resolve."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict


@dataclass
class Node:
    value: int
    children: list[Node] = field(default_factory=list)


@dataclass
class Pair:
    label: str
    left: Pair | None = None
    right: Pair | None = None


class NodeDict(TypedDict):
    value: int
    children: list[NodeDict]


def size(t: Node) -> int:
    """How many nodes the tree holds."""
    return 1 + sum(size(c) for c in t.children)


def height(t: Node) -> int:
    """The longest path from the root, counted in nodes."""
    return 1 + max((height(c) for c in t.children), default=0)


def mirror(t: Node) -> Node:
    """The tree with every node's children reversed."""
    return Node(t.value, [mirror(c) for c in reversed(t.children)])


NODE_SCHEMA = {
    "title": "JsonNode",
    "type": "object",
    "properties": {
        "value": {"type": "integer"},
        "children": {"type": "array", "items": {"$ref": "#"}},
    },
    "required": ["value", "children"],
    "additionalProperties": False,
}

TREE_SCHEMA = {
    "title": "JsonTree",
    "type": "object",
    "properties": {"root": {"$ref": "#/$defs/Branch"}},
    "required": ["root"],
    "additionalProperties": False,
    "$defs": {
        "Branch": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "kids": {"type": "array", "items": {"$ref": "#/$defs/Branch"}, "maxItems": 3},
            },
            "required": ["name", "kids"],
            "additionalProperties": False,
        }
    },
}
