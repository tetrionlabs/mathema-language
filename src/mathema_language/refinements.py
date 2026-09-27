# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The refinement keys this package serves inside `L[...]`, each
registered under mathema's `mathema.language_refinements` group and
built from mathema's `RefinedLanguage` kit.

- `len`: the length in code points, Python's `len`; the plain member of
  length `n` is one repeated simple character the language admits
  (`"a" * 80`), a built member a run of the language's own members cut
  to length.
- `depth`, `nodes`, `children`: the structure of a nested member. On a
  row language they count records (`schema.structure`): records along
  the deepest path, records in all, and the most records one record
  holds directly. On `L[json]` they count as `vocabulary.tree` does,
  every container a level and every value a node, measured off the text
  so any depth is read. On a language of plain text they are refused. The
  plain member at a bound for `L[json]` is the simplest document with
  that measure (`[[[]]]` for depth 3), and built members are random
  documents of exactly that measure."""
from __future__ import annotations

import random
from typing import Any

from ._surface import RefinedLanguage, domain_bound_from_json

_SIMPLE = ("a", "0", "x", "A", " ")


def _range(interval: Any) -> tuple[int, int | None]:
    lo, hi = interval[0], interval[1]
    first = int(lo) if getattr(interval, "closed_lo", True) else int(lo) + 1
    if hi == float("inf"):
        return first, None
    return first, int(hi) if getattr(interval, "closed_hi", True) else int(hi) - 1


def length(language: Any, interval: Any) -> Any:
    """The members of `language` whose length in code points lies in
    `interval`."""

    def plain(n: int) -> str | None:
        for ch in _SIMPLE:
            if language.contains(ch * n):
                return ch * n
        return None

    def build(rng: random.Random, n: int) -> str | None:
        for _ in range(100):
            s = language.sample(rng)
            if isinstance(s, str) and len(s) == n:
                return s
        for _ in range(100):
            run = ""
            while len(run) < n:
                piece = language.sample(rng)
                if not isinstance(piece, str):
                    return None
                run += piece or _SIMPLE[0]
            if language.contains(run[:n]):
                return run[:n]
        return None

    lo, hi = _range(interval)
    schema = {"minLength": lo, **({"maxLength": hi} if hi is not None else {})}
    return RefinedLanguage(language, "len", interval, measure=len, plain=plain, build=build,
                           schema=schema, hazard_kind="length")


def length_bound(lo: int, hi: int | None) -> Any:
    """The interval of lengths from `lo` to `hi` (None for no upper
    bound), as a refinement reads it."""
    return domain_bound_from_json({"lo": float(lo), "hi": float("inf") if hi is None else float(hi),
                                   "closed_lo": True, "closed_hi": True})


_STRUCTURE_KEYS = {"depth": 0, "nodes": 1, "children": 2}


def _denotes_json(language: Any) -> bool:
    base = language
    while hasattr(base, "base"):
        base = base.base
    return getattr(base, "name", None) == "json"


def _structure_measure(language: Any, key: str) -> Any:
    """The measure `key` takes of a member of `language`."""
    from .text.json_structure import scan
    from .vocabulary.tree import _walk

    index = _STRUCTURE_KEYS[key]
    if _denotes_json(language):
        return lambda value: scan(value)[index] if isinstance(value, str) else None
    if getattr(language, "kind", None) in ("string",):
        raise ValueError(
            f"{key} measures the structure of a nested value; L[{language.name}] "
            "is plain text. Refine a language of nested values: L[json], or a row "
            "or schema language")
    base = _row_base(language)
    if base is not None:
        from .schema.structure import record_measures
        return lambda value: record_measures(base.schema, value)[index]
    return lambda value: _walk(value)[index]


def _row_base(language: Any) -> Any:
    """The row language beneath any refinements, or None."""
    base = language
    while hasattr(base, "base"):
        base = base.base
    return base if getattr(base, "kind", None) == "row" and hasattr(base, "schema") else None


def _json_plain(key: str, n: int) -> str | None:
    if n < 0:
        return None
    if key == "depth":
        return "[" * n + "]" * n if n else "0"
    if key == "nodes":
        return None if n == 0 else "0" if n == 1 else "[" + ",".join(["0"] * (n - 1)) + "]"
    return "[" + ",".join(["0"] * n) + "]"


def _json_build(key: str, rng: random.Random, n: int) -> str | None:
    """A random JSON document whose `key` measure is exactly `n`."""
    import json

    def scalar() -> Any:
        return rng.choice([0, 1, -1, 2.5, "a", "", True, False, None])

    if key == "depth":
        value: Any = scalar()
        for _ in range(n):
            extra = [scalar() for _ in range(rng.randint(0, 3))]
            if rng.random() < 0.5:
                value = [*extra[:1], value, *extra[1:]]
            else:
                value = {"k": value, **{f"v{i}": x for i, x in enumerate(extra)}}
        return json.dumps(value)
    if key == "nodes":
        if n < 1:
            return None
        # a random tree of exactly n nodes: each new node hangs under an
        # earlier one, and a node with children is a container
        parents = [rng.randrange(i) for i in range(1, n)]
        kids: dict[int, list[int]] = {}
        for child, parent in enumerate(parents, start=1):
            kids.setdefault(parent, []).append(child)
        built: dict[int, Any] = {}
        for node in range(n - 1, -1, -1):
            below = [built[k] for k in kids.get(node, [])]
            built[node] = below if node in kids else scalar()
        return json.dumps(built[0])
    width = n
    rows = [scalar() for _ in range(width)]
    for i in range(len(rows)):
        if rng.random() < 0.3:
            rows[i] = [scalar() for _ in range(rng.randint(0, max(0, width)))]
    return json.dumps(rows)


def _row_member(language: Any, key: str, n: int) -> Any:
    """A member of a recursive row language whose `key` measure is
    exactly `n`, from its one-chain spines and its single wide node, or
    None when neither shape has that measure."""
    base = _row_base(language)
    if n < 0 or base is None or not hasattr(base, "_spine"):
        return None
    measure = _structure_measure(language, key)
    shapes = (base._wide,) if key == "children" else (base._spine, base._wide)
    for shape in shapes:
        size = 0 if shape == base._wide else 1
        while size <= n + 2:
            candidate = shape(size)
            if candidate is None:
                break
            measured = measure(candidate)
            if measured == n:
                return candidate
            if measured > n:
                break
            size += 1
    return None


def structure(key: str) -> Any:
    """The refinement for `key` in `depth`, `nodes`, `children`."""

    def refine(language: Any, interval: Any) -> Any:
        measure = _structure_measure(language, key)
        json_text = _denotes_json(language)
        return RefinedLanguage(
            language, key, interval, measure=measure,
            plain=(lambda n: _json_plain(key, n)) if json_text else
            (lambda n: _row_member(language, key, n)),
            build=(lambda rng, n: _json_build(key, rng, n)) if json_text else None,
            schema={"x-mathema": {key: [_range(interval)[0], _range(interval)[1]]}},
            hazard_kind="shape")

    return refine


depth = structure("depth")
nodes = structure("nodes")
children = structure("children")


__all__ = ["children", "depth", "length", "length_bound", "nodes"]
