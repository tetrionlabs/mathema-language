# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Table operations for claims over frame languages, bound with
`let`, each over the plain reading of a table (a list of records,
mapping or attribute rows) and carrying a neutral id in
`__mathema_vocabulary__` (`table.rows@1`) that a dataframe runtime
maps to its own implementation of the same meaning.
"""
from __future__ import annotations

import math
import random
from collections.abc import Sequence
from typing import Any


def _get(row: Any, column: str) -> Any:
    return row.get(column) if isinstance(row, dict) else getattr(row, column, None)


def _is_null(value: Any) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def rows(frame: Sequence[Any]) -> int:
    """How many rows the table holds."""
    return len(frame)


def columns(frame: Sequence[Any]) -> tuple[str, ...]:
    """The column names, in first-seen order over the rows."""
    names: list[str] = []
    for row in frame:
        keys = row.keys() if isinstance(row, dict) else (
            vars(row).keys() if hasattr(row, "__dict__") else ())
        for k in keys:
            if str(k) not in names:
                names.append(str(k))
    return tuple(names)


def nulls(frame: Sequence[Any], column: str) -> int:
    """How many cells of `column` are null (None or NaN)."""
    return sum(1 for row in frame if _is_null(_get(row, column)))


def unique(frame: Sequence[Any], *cols: str) -> bool:
    """Whether the tuples over `cols` are distinct across the rows."""
    seen: set[Any] = set()
    for row in frame:
        key = tuple(_hashable(_get(row, c)) for c in cols)
        if key in seen:
            return False
        seen.add(key)
    return True


def sorted_by(frame: Sequence[Any], column: str) -> bool:
    """Whether the rows are in non-decreasing order of `column`."""
    values = [_get(row, column) for row in frame]
    try:
        return all(a <= b for a, b in zip(values, values[1:], strict=False))
    except TypeError:
        return False


def project(frame: Sequence[Any], *cols: str) -> list[dict[str, Any]]:
    """The rows reduced to `cols`, as mappings."""
    return [{c: _get(row, c) for c in cols} for row in frame]


def permute(frame: Sequence[Any], seed: int = 0) -> list[Any]:
    """The rows in a shuffled order decided by `seed`."""
    out = list(frame)
    random.Random(seed).shuffle(out)
    return out


def sum_of(frame: Sequence[Any], column: str) -> Any:
    """The sum of `column` over the rows, nulls skipped."""
    return sum(v for v in (_get(row, column) for row in frame) if not _is_null(v))


def frame_eq(a: Sequence[Any], b: Sequence[Any], *, order: bool = True,
             nan: str = "equal", null: str = "equal",
             columns: Sequence[str] | None = None, tolerance: float = 0.0) -> bool:
    """Whether two tables hold the same rows: in the same order or as
    multisets (`order`), NaN equal to NaN or never (`nan`), null
    equal to null or never (`null`), over `columns` or every column,
    numbers within `tolerance`."""
    cols = tuple(columns) if columns is not None else _shared_columns(a, b)

    def cell_eq(x: Any, y: Any) -> bool:
        if x is None or y is None:
            return null == "equal" and x is None and y is None
        if isinstance(x, float) and isinstance(y, float) and math.isnan(x) and math.isnan(y):
            return nan == "equal"
        if isinstance(x, (int, float)) and isinstance(y, (int, float)) and not isinstance(x, bool):
            return abs(x - y) <= tolerance
        return bool(x == y)

    def row_eq(r: Any, s: Any) -> bool:
        return all(cell_eq(_get(r, c), _get(s, c)) for c in cols)

    if len(a) != len(b):
        return False
    if order:
        return all(row_eq(r, s) for r, s in zip(a, b, strict=True))
    unmatched = list(b)
    for r in a:
        for i, s in enumerate(unmatched):
            if row_eq(r, s):
                del unmatched[i]
                break
        else:
            return False
    return not unmatched


def _shared_columns(a: Sequence[Any], b: Sequence[Any]) -> tuple[str, ...]:
    ca, cb = columns(a), columns(b)
    return tuple(c for c in ca if c in cb) + tuple(c for c in cb if c not in ca)


def _hashable(value: Any) -> Any:
    try:
        hash(value)
        return value
    except TypeError:
        return repr(value)


VOCABULARY: dict[str, object] = {
    "rows": rows, "columns": columns, "nulls": nulls, "unique": unique,
    "sorted_by": sorted_by, "project": project, "permute": permute,
    "sum_of": sum_of, "frame_eq": frame_eq,
}

for _name, _fn in VOCABULARY.items():
    _fn.__mathema_vocabulary__ = f"table.{_name}@1"  # type: ignore[attr-defined]

__all__ = ["VOCABULARY", "columns", "frame_eq", "nulls", "permute", "project", "rows",
           "sorted_by", "sum_of", "unique"]
