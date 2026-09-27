# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Self-referential schemas the recursive-schema tests run over, at
module level so their forward references resolve."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, TypedDict


class Ge:
    def __init__(self, ge):
        self.ge = ge


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


def double_size(t: Node) -> int:
    """Twice the node count, counted recursively."""
    return 2 + sum(double_size(c) for c in t.children)


def leaves_plus(t: Node) -> int:
    """The child count plus one per level, a fold that is 1 at a leaf."""
    return 1 + len(t.children) + sum(leaves_plus(c) for c in t.children)


@dataclass
class Weighted:
    weight: Annotated[int, Ge(0)]
    kids: list[Weighted] = field(default_factory=list)


def weight_total(t: Weighted) -> int:
    """Every node's weight, summed."""
    return t.weight + sum(weight_total(c) for c in t.kids)


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
