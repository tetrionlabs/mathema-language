# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Structure of nested values, for claims about nesting: `depth`,
`nodes`, `width` and `leaves`. On a record tree (a dataclass or a
pydantic model whose fields hold more of its records) they count
records, exactly as the refinement keys of the same names do: a record
with no child records has depth 1, is one node and one leaf, and width
is the most child records any one record holds. On any other nest of
dicts, lists, tuples and sets, which has no schema to say what a record
is, they count containers and values: a scalar has depth 0 and is one
node, a container has depth one more than its deepest child (so `[]`
has depth 1). Every walk is iterative, so a value nested far past the
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
    """(depth, nodes, width, leaves) of `value` in containers and
    values, iteratively; a
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


def _measure(value: Any) -> tuple[int, int, int, int]:
    """(depth, nodes, width, leaves): in records for a record tree, in
    containers and values for any other nest."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type) \
            or isinstance(getattr(type(value), "model_fields", None), dict):
        from ..schema.adaptors import adapt_row
        from ..schema.structure import record_structure
        language = adapt_row(type(value))
        if language is not None and getattr(language, "schema", None) is not None:
            return record_structure(language.schema, value)
    return _walk(value)


def depth(value: Any) -> int:
    """Nesting levels: records along the deepest path of a record tree,
    else containers (0 for a scalar, 1 for a flat container)."""
    return _measure(value)[0]


def nodes(value: Any) -> int:
    """The records in a record tree, else every value and container,
    counted once per place it appears."""
    return _measure(value)[1]


def width(value: Any) -> int:
    """The most children any one node has: child records in a record
    tree, else the items or values of one container; 0 for a scalar."""
    return _measure(value)[2]


def leaves(value: Any) -> int:
    """The nodes with no children: records holding no other record, or
    scalars and empty containers."""
    return _measure(value)[3]


VOCABULARY: dict[str, object] = {
    "depth": depth, "nodes": nodes, "width": width, "leaves": leaves,
}

for _name, _fn in VOCABULARY.items():
    _fn.__mathema_vocabulary__ = f"tree.{_name}@1"  # type: ignore[attr-defined]

__all__ = ["VOCABULARY", "depth", "leaves", "nodes", "width"]
