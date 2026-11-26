# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A record's draws, taken through the language core resolves for
`L[...]`, fall inside every bound its fields declare, at every nesting
depth and in every adaptor that states bounds (a dataclass and a
TypedDict through `Annotated` markers, a pydantic `Field(ge=, le=)`, a
JSON Schema `minimum`/`maximum`); they reach both endpoints of each
bound and spread over the range between them."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

import pytest
from annotated_types import Ge, Gt, Le, Lt

pydantic = pytest.importorskip("pydantic")
pytest.importorskip("jsonschema")

from mathema.languages import resolve_language  # noqa: E402

DRAWS = 500
SEED = 20261125
BINS = 10

PRICE = (0.0, 10.0)
HOURS = (0, 24)
FIXED = (0.0, 100.0)


@dataclass
class Runner:
    price: Annotated[float, Ge(0), Le(10)]
    hours: Annotated[int, Ge(0), Le(24)]


@dataclass
class Layers:
    runner: Runner
    fixed: Annotated[float, Ge(0), Le(100)]


@dataclass
class Stack:
    """Three records deep, a list of records and an optional record."""
    layers: Layers
    spares: list[Runner]
    backup: Runner | None


class TRunner(TypedDict):
    price: Annotated[float, Ge(0), Le(10)]
    hours: Annotated[int, Ge(0), Le(24)]


class TLayers(TypedDict):
    runner: TRunner
    fixed: Annotated[float, Ge(0), Le(100)]


class MRunner(pydantic.BaseModel):
    price: float = pydantic.Field(ge=0, le=10)
    hours: int = pydantic.Field(ge=0, le=24)


class MLayers(pydantic.BaseModel):
    runner: MRunner
    fixed: float = pydantic.Field(ge=0, le=100)


class MStack(pydantic.BaseModel):
    layers: MLayers
    spares: list[MRunner]
    backup: MRunner | None


_RUNNER_SCHEMA = {"type": "object", "required": ["price", "hours"],
                  "properties": {"price": {"type": "number", "minimum": 0, "maximum": 10},
                                 "hours": {"type": "integer", "minimum": 0, "maximum": 24}}}
LAYERS_SCHEMA = {"title": "JLayers", "type": "object", "required": ["runner", "fixed"],
                 "properties": {"runner": _RUNNER_SCHEMA,
                                "fixed": {"type": "number", "minimum": 0, "maximum": 100}}}
STACK_SCHEMA = {"title": "JStack", "type": "object", "required": ["layers", "spares", "backup"],
                "properties": {"layers": LAYERS_SCHEMA,
                               "spares": {"type": "array", "items": _RUNNER_SCHEMA},
                               "backup": {"anyOf": [_RUNNER_SCHEMA, {"type": "null"}]}}}


@dataclass
class Open:
    """Exclusive bounds: every draw strictly between them."""
    rate: Annotated[float, Gt(0), Lt(1)]
    count: Annotated[int, Gt(0), Lt(5)]


_HERE = __name__
LAYERS = [f"{_HERE}.Layers", f"{_HERE}.TLayers", f"{_HERE}.MLayers", f"{_HERE}.LAYERS_SCHEMA"]
STACKS = [f"{_HERE}.Stack", f"{_HERE}.MStack", f"{_HERE}.STACK_SCHEMA"]


def _get(value: Any, name: str) -> Any:
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _runner_values(runner: Any) -> dict[str, Any]:
    return {"price": _get(runner, "price"), "hours": _get(runner, "hours")}


def _layers_values(layers: Any, path: str) -> list[tuple[str, Any]]:
    runner = _runner_values(_get(layers, "runner"))
    return [(f"{path}.runner.price", runner["price"]), (f"{path}.runner.hours", runner["hours"]),
            (f"{path}.fixed", _get(layers, "fixed"))]


def _bounds(path: str) -> tuple[float, float]:
    leaf = path.rsplit(".", 1)[1]
    return {"price": PRICE, "hours": HOURS, "fixed": FIXED}[leaf]


def _draws(ref: str) -> list[Any]:
    language = resolve_language(ref)
    rng = random.Random(SEED)
    return [language.sample(rng) for _ in range(DRAWS)]


def _leaves(ref: str) -> dict[str, list[Any]]:
    """Every bounded leaf of every draw, keyed by its path in the record."""
    out: dict[str, list[Any]] = {}
    stacked = ref in STACKS
    for value in _draws(ref):
        pairs = []
        if stacked:
            pairs += _layers_values(_get(value, "layers"), "layers")
            for spare in _get(value, "spares"):
                pairs += [(f"spares[].{k}", v) for k, v in _runner_values(spare).items()]
            backup = _get(value, "backup")
            if backup is not None:
                pairs += [(f"backup.{k}", v) for k, v in _runner_values(backup).items()]
        else:
            pairs += _layers_values(value, "layers")
        for path, v in pairs:
            out.setdefault(path, []).append(v)
    return out


@pytest.mark.parametrize("ref", LAYERS + STACKS)
def test_every_draw_is_inside_its_declared_bounds_at_every_depth(ref):
    leaves = _leaves(ref)
    assert leaves
    for path, values in leaves.items():
        lo, hi = _bounds(path)
        outside = [v for v in values if not lo <= v <= hi]
        assert not outside, f"{ref} {path}: {len(outside)}/{len(values)} outside [{lo}, {hi}], e.g. {outside[:3]}"


@pytest.mark.parametrize("ref", LAYERS + STACKS)
def test_both_endpoints_of_every_bound_are_drawn(ref):
    for path, values in _leaves(ref).items():
        lo, hi = _bounds(path)
        assert lo in values, f"{ref} {path}: the lower bound {lo} never drawn in {len(values)}"
        assert hi in values, f"{ref} {path}: the upper bound {hi} never drawn in {len(values)}"


@pytest.mark.parametrize("ref", LAYERS + STACKS)
def test_draws_spread_over_every_tenth_of_the_range(ref):
    for path, values in _leaves(ref).items():
        lo, hi = _bounds(path)
        width = (hi - lo) / BINS
        hit = {min(int((v - lo) / width), BINS - 1) for v in values}
        assert hit == set(range(BINS)), f"{ref} {path}: tenths never drawn {sorted(set(range(BINS)) - hit)}"


def test_exclusive_bounds_are_never_drawn():
    language = resolve_language(f"{_HERE}.Open")
    rng = random.Random(SEED)
    for _ in range(DRAWS):
        row = language.sample(rng)
        assert 0 < row.rate < 1
        assert 0 < row.count < 5


def total(layers) -> float:
    """The runner's cost plus the fixed cost."""
    return layers.runner.price * layers.runner.hours + layers.fixed


def total_forgetting_fixed(layers) -> float:
    """A planted bug: the fixed cost is left out."""
    return layers.runner.price * layers.runner.hours


@pytest.mark.parametrize("ref", LAYERS[:1] + LAYERS[2:3])
def test_a_claim_over_the_declared_bounds_catches_the_planted_bug(ref):
    from mathema.conjecture import check_conjectures, claim
    law = f"for layers in L[{ref}], f(layers) >= layers.fixed"
    (right,) = check_conjectures(total, [claim(law, route="probe")])
    (wrong,) = check_conjectures(total_forgetting_fixed, [claim(law, route="probe")])
    assert right.verdict == "holds", right.note
    assert wrong.verdict == "falsified", wrong.note
