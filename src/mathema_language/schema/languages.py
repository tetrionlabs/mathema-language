# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A schema read as a language: `RowLanguage`, whose members are
single records of the schema in one ecosystem."""
from __future__ import annotations

import random
from collections.abc import Iterable
from typing import Any

from .._surface import HazardValue, LanguageRef, Problem, domain_bound_from_json
from . import generate as _gen
from .checks import check_problems, json_schema
from .ecosystems._base import Ecosystem
from .model import Field, RowSchema, TableSchema

_REJECTION_TRIES = 50


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
        return LanguageRef("unicode", (("len", length),))
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
        #: internal: the table-level facts an ORM adaptor read off its
        #: table (keys, foreign keys), kept for the held table languages
        self._table_defaults: TableSchema | None = None

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


__all__ = ["NoMember", "RowLanguage"]
