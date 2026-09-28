# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A schema read as a language: `RowLanguage`, whose members are
single records of the schema in one ecosystem."""
from __future__ import annotations

import functools
import math
import random
import sys
import threading
from collections.abc import Iterable
from typing import Any, cast

from .._surface import HazardValue, LanguageRef, Problem, domain_bound_from_json
from . import generate as _gen
from .checks import check_problems, json_schema
from .ecosystems._base import Ecosystem
from .model import SAMPLING_BOUNDS, Field, RowSchema, TableSchema

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


def _within_budget(method: Any) -> Any:
    """Run a method that draws nested values under the language's
    draw budget, so a recursive schema's draws resolve its references
    and always end."""
    @functools.wraps(method)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        bounds = getattr(self, "_draw_override", None) or self.sampling
        with _gen.drawing_within(self.schema, depth=bounds["depth"], nodes=bounds["nodes"],
                                 width=bounds["width"]):
            budget = _gen._BUDGET.get()
            if budget is not None and bounds.get("reach"):
                budget["reach"] = True
            return method(self, *args, **kwargs)
    return wrapper


def _ladder(top: int) -> list[int]:
    """Depths 1, 2, 4, ... up to and including `top`."""
    out, d = [], 1
    while d < top:
        out.append(d)
        d *= 2
    return [*out, top]


#: the budget for a schema that does not refer to itself: wide enough
#: never to cut a draw short
_FLAT_BUDGET = {"depth": 64, "nodes": 1_000_000, "width": 1_000_000}


#: marks a validator depth limit not measured yet
_UNMEASURED = object()
#: the stack a measuring thread asks for: a validator recursing to the
#: interpreter's limit needs more C stack than a thread gets by default
_MEASURING_STACK = 64 * 1024 * 1024
#: frames spent before the second measurement of a validator's limit
_PROBE_FRAMES = 100
#: the caller's stack a stated validator limit leaves room for
_CALLER_FRAMES = 250


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
        #: the deepest member the ecosystem's own validator accepts, when
        #: it stops before the interpreter's recursion limit (found while
        #: building the hazards, stated in the persisted form)
        self.validator_depth_limit: int | None = None
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

    @_within_budget
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
        if self.schema.recursive:
            # a recursive schema's draws spread over a depth ladder
            # instead of clustering shallow: each draw aims at a rung the
            # draw's own random stream picks
            ladder = self.sampling["ladder"]
            self._draw_override: dict[str, Any] | None = {
                **self.sampling, "depth": ladder[rng.randrange(len(ladder))], "reach": True}
        try:
            return self._sample(rng)
        finally:
            self._draw_override = None

    def _sample(self, rng: random.Random) -> Any:
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
        flat: tuple[HazardValue, ...] = tuple(self._field_hazards())
        if not self.schema.recursive:
            return flat
        return (*self._structure_hazards(), *flat)

    @_within_budget
    def _field_hazards(self) -> tuple[HazardValue, ...]:
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

    @_within_budget
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

    @_within_budget
    def _record_type(self, t: Any) -> tuple[Any, Any] | None:
        """`(fields, construct)` of a struct or referenced record type,
        or None for any other type."""
        if t.base == "struct":
            return t.fields or (), t.construct
        if t.base == "ref" and t.ref is not None:
            try:
                target = self.schema.definition(t.ref)
            except KeyError:
                return None
            return target.fields, target.construct or t.construct
        return None

    @_within_budget
    def _simpler_records(self, record: tuple[Any, Any], element: Any) -> list[Any]:
        """`element`, a record of the given type, with each of its fields
        in turn moved to its simplest member."""
        fields, construct = record
        present = {g.name: _read(element, g.name)[1] for g in fields if _read(element, g.name)[0]}
        out = []
        for g in fields:
            if g.name not in present:
                continue
            for simple in _gen.simpler(g, present[g.name]):
                if _gen._same(present[g.name], simple):
                    continue
                values = {**present, g.name: simple}
                try:
                    out.append(construct(**values) if construct is not None else values)
                except Exception:
                    continue
        return out

    def shrink(self, value: Any) -> Iterable[Any]:
        """Records one step simpler, each a member itself: a subtree
        hoisted into the root's place, a list element dropped, a record
        in a list with one of its own fields made simpler, or one field
        moved toward its simplest member (the simplest itself, then for
        a number the midpoint and one step)."""
        if not self.contains(value):
            return ()
        out: list[Any] = []
        present_values = {g.name: _read(value, g.name)[1] for g in self.schema.fields
                          if _read(value, g.name)[0]}
        found = self._edge() if self.schema.recursive else None
        if found is not None and not found[2]:
            # structure first: a subtree hoisted into the root's place
            edge = found[1]
            kids = present_values.get(edge.name)
            for kid in (kids if isinstance(kids, list) else [kids] if kids is not None else [])[:8]:
                if self.contains(kid):
                    out.append(kid)
        for f in self.schema.fields:
            current = present_values.get(f.name)
            if isinstance(current, list) and current:
                # one element dropped
                for i in range(min(len(current), 8)):
                    values = dict(present_values)
                    values[f.name] = current[:i] + current[i + 1:]
                    try:
                        row = self._build(values)
                    except Exception:
                        continue
                    if self.contains(row):
                        out.append(row)
        for f in self.schema.fields:
            current = present_values.get(f.name)
            item = f.type.item if f.type.base == "list" else None
            record = self._record_type(item) if item is not None else None
            if record is None or not isinstance(current, list):
                continue
            # a record in the list with one of its own fields simplified
            for i, element in enumerate(current[:8]):
                for smaller in self._simpler_records(record, element):
                    values = dict(present_values)
                    values[f.name] = [*current[:i], smaller, *current[i + 1:]]
                    try:
                        row = self._build(values)
                    except Exception:
                        continue
                    if self.contains(row):
                        out.append(row)
        for f in self.schema.fields:
            present, current = _read(value, f.name)
            if not present:
                continue
            for simple in _gen.simpler(f, current):
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

    def derive(self, *, param: str, lhs: str, relation: str, rhs: str,
               functions: dict[str, Any], refinements: dict[str, Any] | None = None,
               **_: Any) -> Any:
        """The derive strategy a recursive schema supplies: structural
        induction over its children (`mathema_language.induction`), or
        None for a schema that does not refer to itself."""
        if not self.schema.recursive:
            return None
        from ..induction import prove
        depth = (refinements or {}).get("depth")
        depth_bound = None if depth is None or depth[1] is None else int(depth[1])
        return prove(self, param, lhs, relation, rhs, functions, depth_bound)

    def render(self, ascii_mode: bool = True) -> str:
        return f"L[{self.name}]"

    @property
    def sampling(self) -> dict[str, Any]:
        """The bounds random members are drawn within: for a schema that
        refers to itself and states no bound of its own, the published
        sampling bounds and the depth ladder draws climb, which are
        sampling choices and never bounds on the language's members."""
        if not self.schema.recursive:
            return dict(_FLAT_BUDGET)
        return {**SAMPLING_BOUNDS, "ladder": _ladder(SAMPLING_BOUNDS["depth"])}

    # ---- structure of a recursive schema

    def _edge(self) -> tuple[RowSchema, Field, list[Field]] | None:
        """`(record type, edge field, path)`: the record type that refers
        to itself, the field through which it does (a list of it, or an
        optional reference to it), and the root fields leading to it
        (empty when the root itself is that record type)."""
        def self_edge(schema: RowSchema) -> Field | None:
            for f in schema.fields:
                t = f.type
                if t.base == "list" and t.item is not None and t.item.base == "ref" \
                        and t.item.ref in (schema.name, _qual(schema)):
                    return f
                if t.base == "ref" and t.ref in (schema.name, _qual(schema)) and f.nullable:
                    return f
            return None

        edge = self_edge(self.schema)
        if edge is not None:
            return self.schema, edge, []
        for f in self.schema.fields:
            t = f.type.item if f.type.base == "list" else f.type
            if t is not None and t.base == "ref" and t.ref is not None:
                target = self.schema.definition(t.ref)
                inner = self_edge(target)
                if inner is not None:
                    return target, inner, [f]
        return None

    def _simplest_values(self, schema: RowSchema) -> dict[str, Any]:
        return {f.name: _gen.simplest(f) for f in schema.fields}

    def _record(self, schema: RowSchema, values: dict[str, Any]) -> Any:
        return schema.construct(**values) if schema.construct is not None else values

    @_within_budget
    def _spine(self, records: int) -> Any:
        """A member whose recursion is one chain `records` long, built
        bottom up with no recursion."""
        found = self._edge()
        if found is None:
            return None
        schema, edge, path = found
        node = self._record(schema, self._simplest_values(schema))
        for _ in range(records - 1):
            values = self._simplest_values(schema)
            values[edge.name] = [node] if edge.type.base == "list" else node
            node = self._record(schema, values)
        return self._wrap(node, path)

    @_within_budget
    def _wide(self, width: int) -> Any:
        """A member whose recursive node has `width` children."""
        found = self._edge()
        if found is None or found[1].type.base != "list":
            return None
        schema, edge, path = found
        kids = [self._record(schema, self._simplest_values(schema)) for _ in range(width)]
        values = self._simplest_values(schema)
        values[edge.name] = kids
        return self._wrap(self._record(schema, values), path)

    def _wrap(self, node: Any, path: list[Field]) -> Any:
        if not path:
            if self.schema.construct is None and isinstance(node, dict):
                return self._build(node)
            return node
        values = self._simplest_values(self.schema)
        f = path[0]
        values[f.name] = [node] if f.type.base == "list" else node
        return self._build(values)

    def _structure_hazards(self) -> list[HazardValue]:
        from .structure import record_measures

        def tree_depth(value: Any) -> int:
            return record_measures(self.schema, value)[0]

        out: list[HazardValue] = []
        bound = self.sampling
        width_bound = bound["width"]
        found = self._edge()
        if found is not None and found[1].constraints.max_len is not None:
            width_bound = min(width_bound, found[1].constraints.max_len)
        # the deepest member within the sampling depth
        records, deepest = 1, None
        while records <= bound["depth"] + 1:
            candidate = self._spine(records)
            if candidate is None or tree_depth(candidate) > bound["depth"]:
                break
            deepest, records = candidate, records + 1
        if deepest is not None and self.contains(deepest):
            out.append(HazardValue("shape", deepest, "the deepest member within the sampling depth"))
        wide = self._wide(width_bound)
        if wide is not None and self.contains(wide):
            out.append(HazardValue("shape", wide, f"a node with {width_bound} children, the widest drawn"))
        # a spine past the interpreter's recursion limit, or at the
        # ecosystem validator's own limit where that is lower
        past = sys.getrecursionlimit() + 50
        if self._spine(past) is not None:
            limit = self._validator_spine_limit()
            if limit is None:
                out.append(HazardValue("length", self._spine(past),
                                       f"a spine of {past} records, past the recursion limit"))
            else:
                at_limit = self._spine(limit)
                self.validator_depth_limit = tree_depth(at_limit)
                out.append(HazardValue("length", at_limit,
                                       f"a spine of {limit} records, at the validator's own depth limit"))
        return out

    def _validator_spine_limit(self) -> int | None:
        """The records in the longest spine the ecosystem's validator
        accepts from any ordinary call site, or None when it accepts one
        past the interpreter's recursion limit. A validator that recurses
        in Python stops at a depth that depends on how deep the caller's
        stack already is, so the limit is measured once, on a fresh
        thread whose stack starts empty, twice (the second time with
        `_PROBE_FRAMES` already used, which gives the frames the
        validator takes per level), and stated with room left for a
        caller `_CALLER_FRAMES` deep: the same answer wherever the
        language is used, and a spine that long validates from there."""
        cached = self.__dict__.get("_spine_limit", _UNMEASURED)
        if cached is not _UNMEASURED:
            return cast("int | None", cached)
        found: dict[str, int | None] = {}

        past = sys.getrecursionlimit() + 50

        def longest(frames: int) -> int:
            if frames:
                return longest(frames - 1)
            lo, hi = 1, past
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if self.contains(self._spine(mid)):
                    lo = mid
                else:
                    hi = mid
            return lo

        def measure() -> None:
            if self.contains(self._spine(past)):
                found["limit"] = None
                return
            clear = longest(0)
            per_level = _PROBE_FRAMES / max(1, clear - longest(_PROBE_FRAMES))
            found["limit"] = max(1, clear - math.ceil(_CALLER_FRAMES / per_level))

        previous = threading.stack_size(_MEASURING_STACK)
        try:
            worker = threading.Thread(target=measure, name="mathema-language-depth-limit")
            worker.start()
        finally:
            threading.stack_size(previous)
        worker.join()
        self.__dict__["_spine_limit"] = found.get("limit")
        return found.get("limit")

    def to_json(self) -> dict[str, Any]:
        out = json_schema(self.schema)
        if self.schema.recursive:
            out.setdefault("x-mathema", {})["sampling"] = self.sampling
            if self.validator_depth_limit is None:
                self.hazards()
            if self.validator_depth_limit is not None:
                out["x-mathema"]["validator_depth_limit"] = self.validator_depth_limit
        return out


def _qual(schema: RowSchema) -> str:
    construct = schema.construct
    owner = getattr(construct, "__self__", construct)
    return str(getattr(owner, "__qualname__", schema.name))


def _read(row: Any, name: str) -> tuple[bool, Any]:
    if isinstance(row, dict):
        return (name in row, row.get(name))
    return (hasattr(row, name), getattr(row, name, None))


__all__ = ["NoMember", "RowLanguage"]
