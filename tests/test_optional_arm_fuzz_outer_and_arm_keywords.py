# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
# ruff: noqa: UP045, UP007
"""Seeded fuzz of keywords given on a property and on its one non-null `anyOf` or `oneOf` arm,
against jsonschema's draft 2020-12 validator, and of pydantic markers given on a field and inside
its optional arm, against `model_validate`.

A `proven` inclusion must admit no probed value that the older side admits and the newer refuses;
a `falsified` witness must be admitted by the older side and refused by the newer. Probes sit on,
just inside and just outside every bound either side states. Default budget is small;
REVIEW_FUZZ_PAIRS sets the pair count, REVIEW_FUZZ_SEED the seed.
"""
import os
import random
from typing import Annotated, Optional

import pytest

pytest.importorskip("z3")
pytest.importorskip("pydantic")
pytest.importorskip("jsonschema")

import jsonschema  # noqa: E402
from annotated_types import Ge, Gt, Le, Lt, MaxLen, MinLen  # noqa: E402
from pydantic import Field, ValidationError, create_model  # noqa: E402

from mathema_language import smt  # noqa: E402

PAIRS = int(os.environ.get("REVIEW_FUZZ_PAIRS", "40"))
SEED = int(os.environ.get("REVIEW_FUZZ_SEED", "5401"))

NUM_KEYS = ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf")
STR_KEYS = ("minLength", "maxLength", "pattern")
BOUNDS = [0, 1, 2, 3, 4, 5, 6]
PATTERNS = ["^a", "b$", "^[ab]*$"]


def _keywords(rng, kind, n):
    keys = NUM_KEYS if kind != "string" else STR_KEYS
    out = {}
    for key in rng.sample(keys, k=min(n, len(keys))):
        if key == "multipleOf":
            out[key] = rng.choice([1, 2, 3])
        elif key == "pattern":
            out[key] = rng.choice(PATTERNS)
        else:
            out[key] = rng.choice(BOUNDS)
    return out


def draw_property(rng):
    kind = rng.choice(["integer", "number", "string"])
    arm = {"type": kind, **_keywords(rng, kind, rng.randint(0, 2))}
    outer = _keywords(rng, kind, rng.randint(0, 2))
    extra = rng.random()
    if extra < 0.08:
        outer["type"] = kind
    elif extra < 0.12:
        outer["const"] = 3 if kind != "string" else "ab"
        arm["const"] = outer["const"]
    elif extra < 0.16:
        outer["enum"] = [1, 3, 5] if kind != "string" else ["a", "ab"]
    null = {"type": "null"}
    if rng.random() < 0.05:
        null = {"type": "null", "not": {}}
    key = rng.choice(["anyOf", "oneOf"])
    arms = [arm, null] if rng.random() < 0.5 else [null, arm]
    if rng.random() < 0.05:
        arms = [{"type": [kind, "null"], **{k: v for k, v in arm.items() if k != "type"}}, null]
    return {**outer, key: arms}


def draw_plain(rng, like):
    """A plain or nullable property of the same kind as `like`, so pairs meet."""
    arms = like.get("anyOf") or like.get("oneOf")
    kind = next(a["type"] for a in arms if a.get("type") != "null")
    kind = kind[0] if isinstance(kind, list) else kind
    p = {"type": kind, **_keywords(rng, kind, rng.randint(0, 2))}
    return {"anyOf": [p, {"type": "null"}]} if rng.random() < 0.5 else p


def _bounds_of(prop, out):
    if isinstance(prop, dict):
        for k, v in prop.items():
            if k in NUM_KEYS + ("minLength", "maxLength") and isinstance(v, (int, float)):
                out.add(v)
            elif isinstance(v, list):
                for x in v:
                    _bounds_of(x, out)


def probes(props):
    bounds = set()
    for p in props:
        _bounds_of(p, bounds)
    nums = {-1, 0, 7, 100}
    for b in bounds:
        nums |= {b - 1, b - 0.5, b, b + 0.5, b + 1}
    lens = sorted({max(0, int(n)) for n in nums if n == int(n)})
    strs = {""}
    for n in lens[:12]:
        for fill in ("a", "b", "ab"):
            strs.add((fill * n)[:n] if n else "")
            strs.add(("a" + "b" * n)[:max(n, 1)])
    return [None, True, False] + sorted(nums) + sorted(strs) + [[1], {}]


def _js(schema):
    v = jsonschema.Draft202012Validator(schema)
    return lambda d: v.is_valid(d)


def _obj(p):
    return {"type": "object", "required": ["x"], "properties": {"x": p}}


def run_jsonschema(pairs, seed):
    rng = random.Random(f"{seed}-js")
    defects, counts = [], {"proven": 0, "falsified": 0, "unknown": 0, "probes": 0}
    for _ in range(pairs):
        p = draw_property(rng)
        q = draw_plain(rng, p)
        old, new = (p, q) if rng.random() < 0.5 else (q, p)
        older, newer = _obj(old), _obj(new)
        try:
            res = smt._schema_inclusion(older, newer)
        except Exception as e:  # a crash is reported, not hidden
            defects.append(("crash", old, new, repr(e)))
            continue
        counts[res.verdict] += 1
        a, b = _js(older), _js(newer)
        if res.verdict == "proven":
            for v in probes([old, new]):
                counts["probes"] += 1
                if a({"x": v}) and not b({"x": v}):
                    defects.append(("FALSE PROOF", old, new, v))
                    break
        elif res.verdict == "falsified" and not (a(res.witness) and not b(res.witness)):
            defects.append(("UNCONFIRMED WITNESS", old, new, res.witness))
    return defects, counts


MARKS = {"ge": Ge, "gt": Gt, "le": Le, "lt": Lt, "min_length": MinLen, "max_length": MaxLen}


def draw_pydantic(rng):
    kind = rng.choice([int, str])
    names = ["ge", "gt", "le", "lt"] if kind is int else ["min_length", "max_length"]
    arm = {k: rng.choice(BOUNDS) for k in rng.sample(names, k=rng.randint(0, 2))}
    field = {k: rng.choice(BOUNDS) for k in rng.sample(names, k=rng.randint(0, 2))}
    inner = Annotated[(kind, *[MARKS[k](v) for k, v in arm.items()])] if arm else kind
    ann = Optional[inner]
    if field:
        ann = Annotated[ann, Field(**field)]
    return ann, (kind.__name__, arm, field)


def run_pydantic(pairs, seed):
    rng = random.Random(f"{seed}-pyd")
    defects, counts = [], {"proven": 0, "falsified": 0, "unknown": 0, "probes": 0}
    for _ in range(pairs):
        (a_ann, a_spec), (b_ann, b_spec) = draw_pydantic(rng), draw_pydantic(rng)
        if a_spec[0] != b_spec[0]:
            continue
        older = create_model("A", x=(a_ann, ...))
        newer = create_model("B", x=(b_ann, ...))
        try:
            res = smt._schema_inclusion(older, newer)
        except Exception as e:
            defects.append(("crash", a_spec, b_spec, repr(e)))
            continue
        counts[res.verdict] += 1

        def ok(m, d, strict):
            try:
                m.model_validate(d, strict=strict)
                return True
            except ValidationError:
                return False
        vals = [None] + list(range(-1, 9)) + ["a" * n for n in range(9)]
        for strict in (False, True):
            if res.verdict == "proven":
                for v in vals:
                    counts["probes"] += 1
                    if ok(older, {"x": v}, strict) and not ok(newer, {"x": v}, strict):
                        defects.append(("FALSE PROOF", strict, a_spec, b_spec, v))
                        break
            elif res.verdict == "falsified":
                w = res.witness
                if not (ok(older, w, strict) and not ok(newer, w, strict)):
                    defects.append(("UNCONFIRMED WITNESS", strict, a_spec, b_spec, w))
    return defects, counts


@pytest.mark.parametrize("runner", [run_jsonschema, run_pydantic], ids=["jsonschema", "pydantic"])
def test_outer_and_arm_keywords_agree_with_the_library(runner):
    defects, counts = runner(PAIRS, SEED)
    print(runner.__name__, counts, len(defects))
    assert not defects, "\n".join(map(str, defects[:10])) + f"\n({len(defects)} total)"
