# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The structure of a record tree, counted in records: a row language's
`depth` is the number of records along the deepest path from the root
(a record with no nested records has depth 1), `nodes` is the number of
records, and `width` is the most records any one record holds
directly, through a field, a list or a map of them. Which values are
records is read off the schema: a struct field or a reference to a
record type is one, a map or a list is only a carrier, and scalars are
not counted. The walk is iterative, and a record met again on its own
path is a cycle."""
from __future__ import annotations

from typing import Any

from .model import NeutralType, RowSchema


def _value_of(record: Any, name: str) -> Any:
    if isinstance(record, dict):
        return record.get(name)
    return getattr(record, name, None)


def _records_in(root: RowSchema, t: NeutralType, value: Any) -> list[tuple[Any, Any]]:
    """The records a field value of type `t` holds directly, each with
    its field list, looking through lists and maps."""
    out: list[tuple[Any, Any]] = []
    pending = [(t, value)]
    while pending:
        typ, v = pending.pop()
        if v is None:
            continue
        if typ.base == "struct":
            out.append((typ.fields or (), v))
        elif typ.base == "ref" and typ.ref is not None:
            try:
                out.append((root.definition(typ.ref).fields, v))
            except KeyError:
                continue
        elif typ.base == "list" and typ.item is not None and isinstance(v, (list, tuple)):
            pending.extend((typ.item, item) for item in reversed(v))
        elif typ.base == "map" and typ.value is not None and isinstance(v, dict):
            pending.extend((typ.value, item) for item in reversed(list(v.values())))
    return out


def record_structure(schema: RowSchema, value: Any) -> tuple[int, int, int, int]:
    """`(depth, nodes, width, leaves)` of a record of `schema`, in
    records: leaves are the records that hold no other record.

    Raises:
        ValueError: the value contains itself.
    """
    max_depth = nodes = widest = leaves = 0
    on_path: set[int] = set()
    stack: list[tuple[Any, Any, int, bool]] = [(schema.fields, value, 1, False)]
    while stack:
        fields, record, level, leaving = stack.pop()
        if leaving:
            on_path.discard(id(record))
            continue
        if id(record) in on_path:
            raise ValueError("the value contains itself")
        on_path.add(id(record))
        stack.append((fields, record, level, True))
        nodes += 1
        max_depth = max(max_depth, level)
        kids: list[tuple[Any, Any]] = []
        for f in fields:
            kids.extend(_records_in(schema, f.type, _value_of(record, f.name)))
        widest = max(widest, len(kids))
        leaves += not kids
        stack.extend((kf, kv, level + 1, False) for kf, kv in reversed(kids))
    return max_depth, nodes, widest, leaves


def record_measures(schema: RowSchema, value: Any) -> tuple[int, int, int]:
    """`(depth, nodes, width)` of a record of `schema`, in records.

    Raises:
        ValueError: the value contains itself.
    """
    return record_structure(schema, value)[:3]


__all__ = ["record_measures", "record_structure"]
