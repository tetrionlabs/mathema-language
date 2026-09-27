# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The two readings of a schema as a language: `RowLanguage`, whose
members are single records, and `FrameLanguage`, whose members are
tables; and `frame_of`, which lifts a row-shaped object to a table
language bound to a module-level name a claim writes as
`L[myapp.schemas.ORDERS]`."""
from __future__ import annotations

import random
from collections.abc import Iterable
from typing import Any

from .._surface import HazardValue, LanguageRef, Problem, domain_bound_from_json
from . import generate as _gen
from .checks import check_problems, json_schema
from .ecosystems._base import Ecosystem
from .model import Field, ForeignKey, RowSchema, TableSchema

_REJECTION_TRIES = 50
_MAX_FRAME_HAZARD_ROWS = 64


class NoMember(RuntimeError):
    """No member of the language was found in the allowed draws: the
    schema's opaque checks refused every generated value. The message
    carries the counts so a probe can report the gap."""

    def __init__(self, name: str, tries: int, accepted: int = 0) -> None:
        super().__init__(f"L[{name}]: no member found in {tries} draws "
                         f"({accepted} accepted by the schema's checks)")
        self.name, self.tries, self.accepted = name, tries, accepted


def _field_bound(f: Field) -> Any:
    """The one-deep domain of a field for the derive lift: a numeric
    field as its interval (an integer field as an interval of `Z`),
    one side infinite when only the other is bounded, or `Z`, `R` when
    neither is; a string
    field as the unicode language, refined by its length bounds
    (`L[unicode, len <= 8]`); anything else None."""
    t, c = f.type, f.constraints
    if t.base in ("int", "float", "decimal"):
        low, high = c.low, c.high
        if t.base == "int" and t.bits:
            bit_lo, bit_hi = _gen._int_range(f)
            low = bit_lo if low is None else low
            high = bit_hi if high is None else high
        if low is None and high is None:
            return "Z" if t.base == "int" else "R"
        interval = {"lo": float("-inf") if low is None else float(low),
                    "hi": float("inf") if high is None else float(high),
                    "closed_lo": c.min is not None or low is None,
                    "closed_hi": c.max is not None or high is None}
        if c.exclusive_min is not None and c.min is None:
            interval["closed_lo"] = False
        if c.exclusive_max is not None and c.max is None:
            interval["closed_hi"] = False
        if t.base == "int":
            return domain_bound_from_json({"base_type": "Z", "pieces": [interval],
                                           "excluded": [], "explicit_type": True})
        return domain_bound_from_json(interval)
    if t.base == "string":
        if c.min_len is None and c.max_len is None:
            return LanguageRef("unicode")
        length = domain_bound_from_json({
            "lo": float(c.min_len or 0),
            "hi": float("inf") if c.max_len is None else float(c.max_len),
            "closed_lo": True, "closed_hi": True})
        return LanguageRef("unicode", length)
    return None


class RowLanguage:
    """A language whose members are records of `schema` in
    `ecosystem`. Membership is the ecosystem's validation plus the
    schema's opaque checks; generation is per field, filtered by
    rejection through the checks."""

    kind = "row"
    level = "schema"

    def __init__(self, schema: RowSchema, ecosystem: Ecosystem,
                 name: str | None = None) -> None:
        self.schema = schema
        self.ecosystem = ecosystem
        self.name = name or schema.name
        self.accepted = 0
        self.rejected = 0
        #: the table-level facts an ORM adaptor read off its table
        #: (keys, foreign keys), the defaults `frame_of` starts from
        self.table_defaults: TableSchema | None = None

    def __repr__(self) -> str:
        return f"RowLanguage({self.name!r}, {self.ecosystem.name})"

    def explain(self, value: Any) -> list[Problem] | None:
        problems = list(self.ecosystem.validate_row(self.schema, value))
        if not problems:
            problems = check_problems(self.schema.checks, value)
        return problems or None

    def contains(self, value: Any) -> bool:
        return self.explain(value) is None

    def _build(self, values: dict[str, Any]) -> Any:
        return self.ecosystem.build_row(self.schema, values)

    def draw_values(self, rng: random.Random) -> dict[str, Any]:
        """One neutral record: a value per field, absent fields left
        out when they are optional one draw in eight."""
        values: dict[str, Any] = {}
        for f in self.schema.fields:
            if not f.required and rng.random() < 0.125:
                continue
            values[f.name] = _gen.draw(rng, f)
        return values

    def sample(self, rng: random.Random) -> Any:
        for _ in range(_REJECTION_TRIES):
            row = self._build(self.draw_values(rng))
            if self.contains(row):
                self.accepted += 1
                return row
            self.rejected += 1
        raise NoMember(self.name, _REJECTION_TRIES, self.accepted)

    def members(self, limit: int) -> tuple[Any, ...] | None:
        """Every member when the schema is finite and small: fields
        that are bools, categoricals or enumerations only."""
        options: list[list[Any]] = []
        for f in self.schema.fields:
            t, c = f.type, f.constraints
            if c.enum is not None:
                values = list(c.enum)
            elif t.base == "bool":
                values = [False, True]
            elif t.base == "categorical" and t.levels is not None:
                values = list(t.levels)
            else:
                return None
            if f.nullable:
                values.append(None)
            options.append(values)
        total = 1
        for values in options:
            total *= len(values)
            if total > limit:
                return None
        import itertools
        out = []
        for combo in itertools.product(*options):
            row = self._build(dict(zip(self.schema.names, combo, strict=True)))
            if self.contains(row):
                out.append(row)
        return tuple(out)

    def hazards(self) -> tuple[HazardValue, ...]:
        """Per field, one record with that field at each of its
        hazards and every other field at its simplest member; only
        the members survive."""
        base = {f.name: _gen.simplest(f) for f in self.schema.fields}
        out: list[HazardValue] = []
        for f in self.schema.fields:
            for hazard in _gen.hazards(f):
                values = dict(base)
                values[f.name] = hazard.value
                try:
                    row = self._build(values)
                except Exception:
                    continue
                if self.contains(row):
                    out.append(HazardValue(hazard.kind, row, f"{f.name}: {hazard.note}"))
        return tuple(out)

    def outside(self, rng: random.Random) -> Any:
        """A non-member near the boundary: one field at a value that
        breaks it, a required column missing, or an extra column."""
        base = {f.name: _gen.simplest(f) for f in self.schema.fields}
        candidates: list[dict[str, Any]] = []
        fields = list(self.schema.fields)
        rng.shuffle(fields)
        for f in fields:
            found = _gen.outside(rng, f)
            if found is not None:
                values = dict(base)
                values[f.name] = found[0]
                candidates.append(values)
        for f in fields:
            if f.required:
                values = dict(base)
                del values[f.name]
                candidates.append(values)
                break
        if self.schema.column_policy == "exact":
            candidates.append({**base, "__extra__": 1})
        rng.shuffle(candidates)
        for values in candidates:
            try:
                row = self._build(values)
            except Exception:
                continue
            if not self.contains(row):
                return row
        return None

    def shrink(self, value: Any) -> Iterable[Any]:
        """Records with one field moved to its simplest member, each
        a member itself."""
        if not self.contains(value):
            return ()
        out: list[Any] = []
        for f in self.schema.fields:
            present, current = _read(value, f.name)
            if not present:
                continue
            simple = _gen.simplest(f)
            if _gen._same(current, simple):
                continue
            values = {g.name: _read(value, g.name)[1] for g in self.schema.fields
                      if _read(value, g.name)[0]}
            values[f.name] = simple
            try:
                row = self._build(values)
            except Exception:
                continue
            if self.contains(row):
                out.append(row)
        return out

    def fields(self) -> dict[str, Any] | None:
        return {f.name: _field_bound(f) for f in self.schema.fields}

    def render(self, ascii_mode: bool = True) -> str:
        return f"L[{self.name}]"

    def to_json(self) -> dict[str, Any]:
        return json_schema(self.schema)


def _read(row: Any, name: str) -> tuple[bool, Any]:
    if isinstance(row, dict):
        return (name in row, row.get(name))
    return (hasattr(row, name), getattr(row, name, None))


class FrameLanguage:
    """A language whose members are tables of `table.row` in
    `ecosystem`: the row count in range, every row a member, keys
    unique, and the table's opaque checks satisfied. Foreign keys are
    checked when the parent tables are supplied to `validate_frame`
    and generated from a fresh parent otherwise."""

    kind = "frame"
    level = "schema"

    def __init__(self, table: TableSchema, ecosystem: Ecosystem,
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
        return list(self.ecosystem.validate_frame(self.table, value)) or None

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
        return self.ecosystem.build_frame(self.table, columns)

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
        return self.ecosystem.build_frame(self.table, columns)

    def shrink(self, value: Any) -> Iterable[Any]:
        """Tables with one row dropped, then with one cell at its
        simplest member, each a member itself."""
        if not self.contains(value):
            return ()
        n = self.ecosystem.row_count(value)
        names = self.table.row.names
        rows = [{name: self.ecosystem.cell(value, i, name) for name in names} for i in range(n)]
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
    defaults = row.table_defaults
    pk = (primary_key,) if isinstance(primary_key, str) else tuple(primary_key)
    table = TableSchema(row.schema,
                        primary_key=pk or (defaults.primary_key if defaults else ()),
                        unique=tuple(tuple(u) for u in unique) or (defaults.unique if defaults else ()),
                        foreign_keys=tuple(foreign_keys) or (defaults.foreign_keys if defaults else ()),
                        row_count=row_count, checks=tuple(checks), ordered=tuple(ordered))
    return FrameLanguage(table, row.ecosystem, name,
                         {k: v for k, v in parent_languages.items() if v is not None})


__all__ = ["FrameLanguage", "NoMember", "RowLanguage", "frame_of"]
