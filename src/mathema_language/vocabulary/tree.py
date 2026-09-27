# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Structure of nested values, for claims about nesting: `depth`,
`nodes`, `children` and `leaves` over any nest of dicts, lists, tuples,
sets and records (a dataclass, a pydantic model, any object with a
`__dict__` of fields is not walked: only those two record shapes are).
A scalar has depth 0 and is one node; a container has depth one more
than its deepest child (so `[]` has depth 1) and is one node plus its
descendants. Every walk is iterative, so a value nested far past the
interpreter's recursion limit is measured, and a value that contains
itself raises ValueError naming the cycle rather than looping.

Each function carries a neutral id in `__mathema_vocabulary__`
(`tree.depth@1`)."""
from __future__ import annotations

import dataclasses
from typing import Any

_SCALARS = (str, bytes, bytearray, int, float, complex, bool, type(None))


def children_of(value: Any) -> list[Any] | None:
    """The direct children of a container, or None for a scalar: a
    mapping's values, a sequence's or set's elements, a dataclass's or
    pydantic model's field values."""
    if isinstance(value, _SCALARS):
        return None
    if isinstance(value, dict):
        return list(value.values())
    if isinstance(value, (list, tuple, set, frozenset)):
        return list(value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return [getattr(value, f.name) for f in dataclasses.fields(value)]
    fields = getattr(type(value), "model_fields", None)
    if isinstance(fields, dict):
        return [getattr(value, name, None) for name in fields]
    return None


def _walk(value: Any) -> tuple[int, int, int, int]:
    """(depth, nodes, children, leaves) of `value`, iteratively; a
    container met again on its own path is a cycle."""
    max_depth = nodes = widest = leaves = 0
    on_path: set[int] = set()
    stack: list[tuple[Any, int, bool]] = [(value, 0, False)]
    while stack:
        node, level, leaving = stack.pop()
        if leaving:
            on_path.discard(id(node))
            continue
        kids = children_of(node)
        nodes += 1
        if kids is None:
            leaves += 1
            max_depth = max(max_depth, level)
            continue
        if id(node) in on_path:
            raise ValueError(f"the value contains itself at depth {level}")
        max_depth = max(max_depth, level + 1)
        widest = max(widest, len(kids))
        if not kids:
            leaves += 1
            continue
        on_path.add(id(node))
        stack.append((node, level, True))
        for kid in reversed(kids):
            stack.append((kid, level + 1, False))
    return max_depth, nodes, widest, leaves


def depth(value: Any) -> int:
    """Nesting levels: 0 for a scalar, 1 for a flat container."""
    return _walk(value)[0]


def nodes(value: Any) -> int:
    """Every value in the nest, containers and scalars, counted once
    per place it appears."""
    return _walk(value)[1]


def children(value: Any) -> int:
    """The most direct children any one container in the nest has; 0
    for a scalar."""
    return _walk(value)[2]


def leaves(value: Any) -> int:
    """The values with no children: scalars and empty containers."""
    return _walk(value)[3]


VOCABULARY: dict[str, object] = {
    "depth": depth, "nodes": nodes, "children": children, "leaves": leaves,
}

for _name, _fn in VOCABULARY.items():
    _fn.__mathema_vocabulary__ = f"tree.{_name}@1"  # type: ignore[attr-defined]

__all__ = ["VOCABULARY", "children", "children_of", "depth", "leaves", "nodes"]
