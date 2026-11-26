# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Decimal inclusion verdicts agree with pydantic's own validation.

Random pairs of pydantic models with Decimal fields (digit limits, bounds, divisors,
optional, list, map and nested forms, a float beside them) are put to `_schema_inclusion`.
A `proven` pair is probed with Decimal values near every boundary either side states;
none may be admitted by the older model and refused by the newer, lax or strict. A
`falsified` witness must be admitted by the older model and refused by the newer.
The pair count is REVIEW_FUZZ_PAIRS (default 40); the seed is REVIEW_FUZZ_SEED.
"""
import os
import random
from decimal import Decimal
from typing import Annotated

import pytest

pytest.importorskip("z3")
pytest.importorskip("pydantic")

from pydantic import Field, ValidationError, create_model  # noqa: E402

from mathema_language.smt import _schema_inclusion  # noqa: E402

PAIRS = int(os.environ.get("REVIEW_FUZZ_PAIRS", "40"))
SEED = int(os.environ.get("REVIEW_FUZZ_SEED", "52"))
PROBES = int(os.environ.get("REVIEW_FUZZ_PROBES", "300"))


# a decimal spec: dict of max_digits, decimal_places, ge, le, gt, lt, multiple_of

def _rand_bound(rng, s):
    places = rng.choice([0, max(s, 0), s + 1, rng.randint(0, 4)])
    whole = rng.choice([0, 1, 5, 99, 10 ** rng.randint(0, 6), -1, -50, -(10 ** rng.randint(0, 6))])
    frac = rng.randint(0, 10 ** places - 1) if places else 0
    v = Decimal(whole) + (Decimal(frac) / (Decimal(10) ** places) if places else 0)
    return v


def _rand_spec(rng):
    spec = {}
    r = rng.random()
    if r < 0.85:
        p = rng.choice([1, 2, 3, 4, 6, 8, 10, 18, 28, rng.randint(1, 28)])
        s = rng.choice([0, 1, 2, 3, p, p + 1, rng.randint(0, min(p + 2, 28))])
        spec["max_digits"], spec["decimal_places"] = p, s
    elif r < 0.9:
        spec["max_digits"] = rng.randint(1, 10)
    elif r < 0.95:
        spec["decimal_places"] = rng.randint(0, 4)
    s = spec.get("decimal_places", 2)
    for key in ("ge", "le", "gt", "lt"):
        if rng.random() < 0.25:
            spec[key] = _rand_bound(rng, s)
    if rng.random() < 0.05:
        spec["multiple_of"] = rng.choice([Decimal("0.5"), Decimal(2), Decimal("0.01")])
    return spec


def _mutate_spec(rng, spec):
    out = dict(spec)
    for _ in range(rng.randint(0, 3)):
        k = rng.choice(["max_digits", "decimal_places", "ge", "le", "gt", "lt", "drop", "same"])
        if k in ("max_digits", "decimal_places"):
            if k in out:
                out[k] = max(0 if k == "decimal_places" else 1, out[k] + rng.choice([-1, 1, 2, -2]))
        elif k == "drop":
            for key in ("ge", "le", "gt", "lt"):
                out.pop(key, None)
        elif k != "same":
            if k in out and rng.random() < 0.6:
                step = Decimal(10) ** -rng.randint(0, 4)
                out[k] = out[k] + rng.choice([-step, step, 0])
            else:
                out[k] = _rand_bound(rng, out.get("decimal_places", 2))
    return out


# a field shape: ("dec", spec) | ("opt", spec) | ("list", spec, maxlen) | ("dict", spec)
# | ("nested", [shapes]) | ("float", ge or None)

def _rand_shape(rng, depth=0):
    r = rng.random()
    if r < 0.45:
        return ("dec", _rand_spec(rng))
    if r < 0.58:
        return ("opt", _rand_spec(rng))
    if r < 0.70:
        return ("list", _rand_spec(rng), rng.randint(0, 3))
    if r < 0.80:
        return ("dict", _rand_spec(rng))
    if r < 0.90 and depth < 1:
        return ("nested", [_rand_shape(rng, depth + 1) for _ in range(rng.randint(1, 2))])
    return ("float", rng.choice([None, 0.0, -1.5]))


def _mutate_shape(rng, shape):
    kind = shape[0]
    if kind in ("dec", "opt", "dict"):
        return (kind, _mutate_spec(rng, shape[1]))
    if kind == "list":
        return (kind, _mutate_spec(rng, shape[1]), max(0, shape[2] + rng.choice([-1, 0, 0, 1])))
    if kind == "nested":
        return (kind, [_mutate_shape(rng, s) for s in shape[1]])
    return shape


def _field(spec):
    return Field(**{k: v for k, v in spec.items()})


def _annotation(shape, name):
    kind = shape[0]
    if kind == "dec":
        return Annotated[Decimal, _field(shape[1])], ...
    if kind == "opt":
        # the constraint on the optional as a whole; inside the arm, see
        # test_optional_arm_constraints_are_read.py
        return Annotated[Decimal | None, _field(shape[1])], ...
    if kind == "list":
        return Annotated[list[Annotated[Decimal, _field(shape[1])]], Field(max_length=shape[2])], ...
    if kind == "dict":
        return dict[str, Annotated[Decimal, _field(shape[1])]], ...
    if kind == "nested":
        return _model(shape[1], name.capitalize()), ...
    ge = shape[1]
    return (Annotated[float, Field(ge=ge)] if ge is not None else float), ...


def _model(shapes, name="M", strict=False):
    fields = {f"f{i}": _annotation(s, f"{name}f{i}") for i, s in enumerate(shapes)}
    config = {"strict": True} if strict else None
    return create_model(name, __config__=config, **fields) if config else create_model(name, **fields)


def rand_case(rng):
    older = [_rand_shape(rng) for _ in range(rng.randint(1, 3))]
    newer = [_mutate_shape(rng, s) for s in older] if rng.random() < 0.9 else \
        [_rand_shape(rng) for _ in older]
    strict = rng.random() < 0.2
    return older, newer, strict


def build(case):
    older, newer, strict = case
    return _model(older, "Older", strict), _model(newer, "Newer", strict)


def _edge_values(specs):
    vals = {Decimal(0), Decimal("0.0"), Decimal("-0"), Decimal(1), Decimal(-1), Decimal("1E+2"),
            Decimal("1.500"), Decimal("0.001"), Decimal("123456.789")}
    for spec in specs:
        p, s = spec.get("max_digits"), spec.get("decimal_places")
        for sc in {s, (s or 0) + 1, max((s or 0) - 1, 0)} - {None}:
            q = Decimal(10) ** -sc
            if p is not None:
                top = Decimal(10) ** (p - (s or 0)) - q
                vals |= {top, -top, top + q, -top - q, Decimal(10) ** (p - (s or 0))}
            vals |= {q, -q, Decimal(1) + q, Decimal("7") * q}
        for key in ("ge", "le", "gt", "lt"):
            if key in spec:
                b = spec[key]
                for d in (0, 1, 2, 3, 4):
                    e = Decimal(10) ** -d
                    vals |= {b, b + e, b - e}
    return sorted(vals)


def _specs(shape):
    kind = shape[0]
    if kind in ("dec", "opt", "list", "dict"):
        return [shape[1]]
    if kind == "nested":
        return [sp for s in shape[1] for sp in _specs(s)]
    return []


def _sample(rng, oshape, nshape, pool):
    kind = oshape[0]
    if kind == "dec":
        return rng.choice(pool)
    if kind == "opt":
        return None if rng.random() < 0.15 else rng.choice(pool)
    if kind == "list":
        return [rng.choice(pool) for _ in range(rng.randint(0, oshape[2] + 1))]
    if kind == "dict":
        return {"a": rng.choice(pool)} if rng.random() < 0.8 else {}
    if kind == "nested":
        npart = nshape[1] if nshape[0] == "nested" else oshape[1]
        return {f"f{i}": _sample(rng, s, npart[i] if i < len(npart) else s, pool)
                for i, s in enumerate(oshape[1])}
    return rng.choice([0.0, 1.5, -1.5, -2.0, 3.0])


def admits(model, record, strict):
    try:
        model.model_validate(record, strict=strict)
        return True
    except ValidationError:
        return False


def probe(case, A, B, rng, n=PROBES):
    """Returns records older admits and newer refuses, with the mode."""
    older, newer, strict = case
    specs = [sp for s in older + newer for sp in _specs(s)]
    pool = _edge_values(specs)
    bad = []
    for _ in range(n):
        rec = {f"f{i}": _sample(rng, s, newer[i], pool) for i, s in enumerate(older)}
        for mode in ([True] if strict else [False, True]):
            if admits(A, rec, mode) and not admits(B, rec, mode):
                bad.append((mode, rec))
    return bad


def run_pairs(pairs=PAIRS, seed=SEED, probes=PROBES):
    """Yields (index, case, verdict, reason, witness, problems)."""
    rng = random.Random(seed)
    for i in range(pairs):
        case = rand_case(rng)
        A, B = build(case)
        result = _schema_inclusion(A, B)
        problems = []
        if result.verdict == "proven":
            problems = [("proven but", m, r) for m, r in probe(case, A, B, random.Random(i), probes)]
        elif result.verdict == "falsified":
            w = result.witness
            modes = [True] if case[2] else [False, True]
            if not any(admits(A, w, m) and not admits(B, w, m) for m in modes):
                problems = [("witness not confirmed", None, w)]
        yield i, case, result.verdict, result.reason, result.witness, problems


def test_decimal_inclusion_verdicts_agree_with_pydantic():
    failures = []
    for i, case, verdict, reason, witness, problems in run_pairs():
        if problems:
            failures.append((i, case, verdict, problems[:2]))
    assert not failures, failures[:3]
