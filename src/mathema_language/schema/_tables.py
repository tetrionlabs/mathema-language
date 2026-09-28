# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Internal and held: table languages. `FrameLanguage`, whose members
are tables of a row schema, `frame_of`, which builds one from a
row-shaped object, and `TableEcosystem`, the table half of an
ecosystem. None of this is part of the package's public surface; the
code and its tests are kept, and nothing outside this package should
import it."""
from __future__ import annotations

import random
from collections.abc import Iterable
from typing import Any, Protocol, runtime_checkable

from .._surface import HazardValue, Problem
from . import generate as _gen
from .checks import json_schema
from .ecosystems._base import Ecosystem
from .languages import _REJECTION_TRIES, NoMember, RowLanguage
from .model import ForeignKey, TableSchema

_MAX_FRAME_HAZARD_ROWS = 64


@runtime_checkable
class TableEcosystem(Ecosystem, Protocol):
    """An ecosystem that also builds and validates tables: `_build_frame`
    makes a table from neutral columns, `_validate_frame` reports every
    problem with one, and `_row_count`, `_column_names` and `_cell`
    read a table."""

    def _build_frame(self, table: TableSchema, columns: dict[str, list[Any]]) -> Any: ...

    def _validate_frame(self, table: TableSchema, frame: Any,
                        parents: dict[str, Any] | None = None) -> list[Problem]: ...

    def _row_count(self, frame: Any) -> int: ...

    def _column_names(self, frame: Any) -> tuple[str, ...] | None: ...

    def _cell(self, frame: Any, i: int, column: str) -> Any: ...


class FrameLanguage:
    """A language whose members are tables of `table.row` in
    `ecosystem`: the row count in range, every row a member, keys
    unique, and the table's opaque checks satisfied. Foreign keys are
    checked when the parent tables are supplied to `validate_frame`
    and generated from a fresh parent otherwise."""

    kind = "table"
    level = "schema"

    def __init__(self, table: TableSchema, ecosystem: TableEcosystem,
                 name: str | None = None,
                 parents: dict[str, RowLanguage] | None = None) -> None:
        self.table = table
        self.ecosystem = ecosystem
        self.name = name or f"{table.name}_frame"
        self.rows = RowLanguage(table.row, ecosystem, table.name)
        self.parents = parents or {}
        self.accepted = 0
        self.rejected = 0

    def __repr__(self) -> str:
        return f"FrameLanguage({self.name!r}, {self.ecosystem.name})"

    def explain(self, value: Any) -> list[Problem] | None:
        return list(self.ecosystem._validate_frame(self.table, value)) or None

    def contains(self, value: Any) -> bool:
        return self.explain(value) is None

    def _count(self, rng: random.Random) -> int:
        lo, hi = self.table.row_count
        top = hi if hi is not None else lo + 8
        if rng.random() < 0.125:
            return rng.choice((lo, min(top, _MAX_FRAME_HAZARD_ROWS)))
        return rng.randint(lo, min(top, _MAX_FRAME_HAZARD_ROWS))

    def _rows_with_keys(self, rng: random.Random, n: int) -> list[dict[str, Any]]:
        """`n` neutral records whose key sets are distinct, redrawing
        the key columns of a clash."""
        rows: list[dict[str, Any]] = []
        seen: dict[tuple[str, ...], set[Any]] = {cols: set() for cols in self.table.key_sets}
        for f in self.table.row.fields:
            if f.unique:
                seen.setdefault((f.name,), set())
        parent_keys = self._parent_keys(rng)
        for _ in range(n):
            for _attempt in range(_REJECTION_TRIES):
                values = self.rows.draw_values(rng)
                for fk in self.table.foreign_keys:
                    keys = parent_keys.get(fk.parent)
                    if keys:
                        chosen = rng.choice(keys)
                        for col, pcol in zip(fk.columns, fk.parent_columns, strict=True):
                            values[col] = chosen[pcol]
                clash = False
                for cols, used in seen.items():
                    key = tuple(_hashable(values.get(c)) for c in cols)
                    if key in used:
                        clash = True
                        break
                if not clash:
                    for cols, used in seen.items():
                        used.add(tuple(_hashable(values.get(c)) for c in cols))
                    rows.append(values)
                    break
        return rows

    def _parent_keys(self, rng: random.Random) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for fk in self.table.foreign_keys:
            parent = self.parents.get(fk.parent)
            if parent is None:
                continue
            keys: list[dict[str, Any]] = []
            for _ in range(4):
                values = parent.draw_values(rng)
                keys.append({c: values.get(c) for c in fk.parent_columns})
            out[fk.parent] = keys
        return out

    def _build(self, rows: list[dict[str, Any]]) -> Any:
        names = self.table.row.names
        columns = {name: [row.get(name) for row in rows] for name in names}
        return self.ecosystem._build_frame(self.table, columns)

    def sample(self, rng: random.Random) -> Any:
        for _ in range(_REJECTION_TRIES):
            frame = self._build(self._rows_with_keys(rng, self._count(rng)))
            if self.contains(frame):
                self.accepted += 1
                return frame
            self.rejected += 1
        raise NoMember(self.name, _REJECTION_TRIES, self.accepted)

    def members(self, limit: int) -> tuple[Any, ...] | None:
        return None

    def hazards(self) -> tuple[HazardValue, ...]:
        """The empty table where the count allows it, one row, the
        smallest and largest counts, every nullable column all null,
        duplicated non-key rows, and one table per row hazard."""
        rng = random.Random(0)
        lo, hi = self.table.row_count
        base = {f.name: _gen.simplest(f) for f in self.table.row.fields}
        out: list[HazardValue] = []

        def offer(kind: str, rows: list[dict[str, Any]], note: str) -> None:
            try:
                frame = self._build(rows)
            except Exception:
                return
            if self.contains(frame):
                out.append(HazardValue(kind, frame, note))

        offer("empty", [], "no rows")
        offer("shape", self._rows_with_keys(rng, 1), "one row")
        if lo > 1:
            offer("shape", self._rows_with_keys(rng, lo), f"the fewest rows, {lo}")
        if hi is not None and hi <= _MAX_FRAME_HAZARD_ROWS and hi > 1:
            offer("shape", self._rows_with_keys(rng, hi), f"the most rows, {hi}")
        for f in self.table.row.fields:
            if f.nullable:
                rows = self._rows_with_keys(rng, 3)
                for row in rows:
                    row[f.name] = None
                offer("null", rows, f"{f.name}: null in every row")
        if not self.table.key_sets and not any(f.unique for f in self.table.row.fields):
            offer("duplicate", [dict(base), dict(base)], "two identical rows")
        for f in self.table.row.fields:
            for hazard in _gen.hazards(f):
                rows = self._rows_with_keys(rng, 1) or [dict(base)]
                rows[0][f.name] = hazard.value
                offer(hazard.kind, rows, f"[0].{f.name}: {hazard.note}")
        return tuple(out)

    def outside(self, rng: random.Random) -> Any:
        """A non-member near the boundary: a cell that breaks its
        field, a duplicated key, a count outside the range, a missing
        or an extra column."""
        rows = self._rows_with_keys(rng, max(2, self.table.row_count[0]))
        if not rows:
            rows = [dict(self.rows.draw_values(rng))]
        candidates: list[list[dict[str, Any]]] = []
        fields = list(self.table.row.fields)
        rng.shuffle(fields)
        for f in fields:
            found = _gen.outside(rng, f)
            if found is not None:
                bad = [dict(r) for r in rows]
                bad[0][f.name] = found[0]
                candidates.append(bad)
        for cols in self.table.key_sets:
            if len(rows) >= 2:
                bad = [dict(r) for r in rows]
                for c in cols:
                    bad[1][c] = bad[0][c]
                candidates.append(bad)
        lo, hi = self.table.row_count
        if lo > 0:
            candidates.append(rows[:lo - 1])
        if hi is not None and hi < _MAX_FRAME_HAZARD_ROWS:
            candidates.append(self._rows_with_keys(rng, hi + 1))
        if self.table.row.column_policy == "exact":
            candidates.append([{**r, "__extra__": 1} for r in rows])
        required = [f for f in fields if f.required]
        if required:
            candidates.append([{k: v for k, v in r.items() if k != required[0].name} for r in rows])
        rng.shuffle(candidates)
        for bad in candidates:
            try:
                frame = self._build_ragged(bad)
            except Exception:
                continue
            if not self.contains(frame):
                return frame
        return None

    def _build_ragged(self, rows: list[dict[str, Any]]) -> Any:
        """Build from rows that may carry extra or missing columns."""
        names: list[str] = []
        for row in rows:
            for k in row:
                if k not in names:
                    names.append(k)
        columns = {name: [row.get(name) for row in rows] for name in names}
        return self.ecosystem._build_frame(self.table, columns)

    def shrink(self, value: Any) -> Iterable[Any]:
        """Tables with one row dropped, then with one cell at its
        simplest member, each a member itself."""
        if not self.contains(value):
            return ()
        n = self.ecosystem._row_count(value)
        names = self.table.row.names
        rows = [{name: self.ecosystem._cell(value, i, name) for name in names} for i in range(n)]
        out: list[Any] = []
        for i in range(n):
            try:
                frame = self._build(rows[:i] + rows[i + 1:])
            except Exception:
                continue
            if self.contains(frame):
                out.append(frame)
        for i in range(min(n, 4)):
            for f in self.table.row.fields:
                simple = _gen.simplest(f)
                if _gen._same(rows[i].get(f.name), simple):
                    continue
                changed = [dict(r) for r in rows]
                changed[i][f.name] = simple
                try:
                    frame = self._build(changed)
                except Exception:
                    continue
                if self.contains(frame):
                    out.append(frame)
        return out

    def fields(self) -> dict[str, Any] | None:
        return None

    def render(self, ascii_mode: bool = True) -> str:
        return f"L[{self.name}]"

    def to_json(self) -> dict[str, Any]:
        return json_schema(self.table)


def _hashable(value: Any) -> Any:
    try:
        hash(value)
        return value
    except TypeError:
        return repr(value)


def frame_of(obj: Any, *, primary_key: tuple[str, ...] | str = (),
             unique: tuple[tuple[str, ...], ...] = (),
             foreign_keys: tuple[ForeignKey, ...] = (),
             row_count: tuple[int, int | None] = (0, None),
             checks: tuple[Any, ...] = (), ordered: tuple[str, ...] = (),
             name: str | None = None,
             parents: dict[str, Any] | None = None) -> FrameLanguage:
    """The table language of a row-shaped object (a dataclass, a
    TypedDict, a pydantic model, a JSON Schema, or a `RowLanguage`)
    with the table-level facts a row schema cannot carry. Bind the
    result to a module-level name and a claim writes it as
    `L[myapp.schemas.ORDERS]`."""
    from .adaptors import adapt_row
    row = obj if isinstance(obj, RowLanguage) else adapt_row(obj)
    if row is None:
        raise TypeError(f"no adaptor reads {obj!r} as a row schema")
    parent_languages = {k: (v if isinstance(v, RowLanguage) else adapt_row(v))
                        for k, v in (parents or {}).items()}
    defaults = row._table_defaults
    pk = (primary_key,) if isinstance(primary_key, str) else tuple(primary_key)
    table = TableSchema(row.schema,
                        primary_key=pk or (defaults.primary_key if defaults else ()),
                        unique=tuple(tuple(u) for u in unique) or (defaults.unique if defaults else ()),
                        foreign_keys=tuple(foreign_keys) or (defaults.foreign_keys if defaults else ()),
                        row_count=row_count, checks=tuple(checks), ordered=tuple(ordered))
    ecosystem: Any = row.ecosystem
    return FrameLanguage(table, ecosystem, name,
                         {k: v for k, v in parent_languages.items() if v is not None})


__all__: list[str] = []
