# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
# ruff: noqa: UP045, UP007
"""Seeded fuzz of union shapes against each library's own validation.

JSON Schema properties are drawn as anyOf or oneOf of up to three arms, a null arm spelled
`{"type": "null"}`, `{"enum": [null]}`, `{"const": null}` or `{"type": ["null"]}`, a nullable
`type` list, nested unions, `$ref` arms and constrained array items; pydantic fields as
`Union[int, str, None]`, `Optional[Optional[...]]`, `Annotated` inside a union and `Field` over a
union of constrained arms. A `proven` verdict must survive every probe under
`jsonschema.validate` or `Model.model_validate`, and a `falsified` witness must be admitted by
the older side and refused by the newer one under the same validation.
REVIEW_FUZZ_PAIRS sets the pair count per ecosystem, REVIEW_FUZZ_SEED the seed.
"""
import os
import random
from typing import Annotated, Optional, Union

import pytest

pytest.importorskip("z3")
pytest.importorskip("pydantic")
pytest.importorskip("jsonschema")

import jsonschema  # noqa: E402
from annotated_types import Ge, Le, MaxLen, MinLen  # noqa: E402
from pydantic import Field, ValidationError, create_model  # noqa: E402

from mathema_language import smt  # noqa: E402

PAIRS = int(os.environ.get("REVIEW_FUZZ_PAIRS", "20"))
SEED = int(os.environ.get("REVIEW_FUZZ_SEED", "5402"))

NULL_ARMS = [{"type": "null"}, {"enum": [None]}, {"const": None}, {"type": ["null"]}]
PROBES = [None, -1, 0, 1, 2, 3, 5, 9, 2.5, "", "a", "ab", "abcdef", True, [], [0], [5], [0, 9],
          ["a"], {}, {"a": 1}]


def _bounds(rng, kind):
    out = {"type": kind}
    lo, hi = ("minimum", "maximum") if kind == "integer" else ("minLength", "maxLength")
    if rng.random() < 0.5:
        out[lo] = rng.choice([0, 1, 2])
    if rng.random() < 0.5:
        out[hi] = rng.choice([2, 3, 5])
    if kind == "string" and rng.random() < 0.4:
        out["pattern"] = rng.choice(_BOUND_VALUES["pattern"])
    return out


def js_arm(rng, depth=0):
    roll = rng.random()
    if roll < 0.35:
        return _bounds(rng, "integer")
    if roll < 0.55:
        return _bounds(rng, "string")
    if roll < 0.7:
        return {"type": "array", "items": _bounds(rng, rng.choice(["integer", "string"]))}
    if roll < 0.78:
        return {"$ref": "#/$defs/P"}
    if roll < 0.86 and depth == 0:
        return js_prop(rng, depth + 1)
    if roll < 0.93:
        return {**_bounds(rng, "integer"), "type": ["integer", "null"]}
    return {"enum": rng.choice([[1, 2], [1, None], ["a", 3]])}


def js_prop(rng, depth=0):
    roll = rng.random()
    if roll < 0.15:
        return js_arm(rng, depth)
    if roll < 0.25:
        return {**_bounds(rng, "integer"), "type": ["integer", "null"]}
    key = rng.choice(["anyOf", "oneOf"])
    arms = [js_arm(rng, depth) for _ in range(rng.choice([1, 1, 2]))]
    if rng.random() < 0.8:
        arms.append(rng.choice(NULL_ARMS) if rng.random() < 0.5 else {"type": "null"})
    rng.shuffle(arms)
    prop = {key: arms}
    if rng.random() < 0.2:
        prop.update({k: v for k, v in _bounds(rng, "integer").items() if k != "type"})
    return prop


_BOUND_VALUES = {"minimum": [0, 1, 2], "maximum": [2, 3, 5], "minLength": [0, 1, 2],
                 "maxLength": [2, 3, 5], "pattern": ["^a", "^ab", "^a+$", "b$", "^[ab]{1,2}$"]}


def rebound(rng, node):
    """The same shape as `node` with each bound redrawn, dropped or kept, so narrowing and
    widening of one shape are both exercised."""
    if isinstance(node, list):
        return [rebound(rng, x) for x in node]
    if not isinstance(node, dict):
        return node
    out = {}
    for k, v in node.items():
        if k in _BOUND_VALUES:
            roll = rng.random()
            if roll < 0.3:
                continue
            out[k] = rng.choice(_BOUND_VALUES[k]) if roll < 0.7 else v
        else:
            out[k] = rebound(rng, v)
    if out.get("type") in ("integer", "string") and rng.random() < 0.3:
        lo, hi = ("minimum", "maximum") if out["type"] == "integer" else ("minLength", "maxLength")
        out[rng.choice([lo, hi])] = rng.choice(_BOUND_VALUES[lo] + _BOUND_VALUES[hi])
    return out


def js_schema(prop):
    return {"type": "object", "required": ["f"], "properties": {"f": prop},
            "$defs": {"P": {"type": "integer", "minimum": 3}}}


def js_valid(schema, record):
    try:
        jsonschema.validate(record, schema)
        return True
    except jsonschema.ValidationError:
        return False


I_ARMS = [int, Annotated[int, Ge(2)], Annotated[int, Le(3)], Annotated[int, Field(ge=1, le=5)]]
S_ARMS = [str, Annotated[str, MaxLen(2)], Annotated[str, MinLen(1)]]


def pyd_field(rng):
    roll = rng.random()
    i, s = rng.choice(I_ARMS), rng.choice(S_ARMS)
    if roll < 0.2:
        return Union[i, s, None], ...
    if roll < 0.35:
        return Optional[Optional[i]], ...
    if roll < 0.5:
        return Union[i, None], ...
    if roll < 0.6:
        return Union[i, s], Field(**rng.choice([{"ge": 0}, {"max_length": 3}, {}]))
    if roll < 0.75:
        return Optional[i], Field(**rng.choice([{"ge": 0}, {"le": 4}, {}]))
    if roll < 0.85:
        return Annotated[Optional[i], Field(**rng.choice([{"ge": 1}, {"le": 2}]))], ...
    return Union[Annotated[int, Ge(rng.choice([0, 2]))], Annotated[int, Le(rng.choice([1, 4]))]], ...


def pyd_valid(model, record):
    try:
        model.model_validate(record)
        return True
    except ValidationError:
        return False


def run(eco, pairs, seed):
    rng = random.Random(f"{seed}-{eco}")
    defects, counts = [], {"proven": 0, "falsified": 0, "unknown": 0}
    for n in range(pairs):
        if eco == "jsonschema":
            prop = js_prop(rng)
            other = rebound(rng, prop) if rng.random() < 0.6 else js_prop(rng)
            older, newer = js_schema(prop), js_schema(other)
            valid = js_valid
        else:
            older = create_model(f"O{n}", f=pyd_field(rng))
            newer = create_model(f"N{n}", f=pyd_field(rng))
            valid = pyd_valid
        try:
            result = smt._schema_inclusion(older, newer)
        except Exception as e:  # a crash is reported, never hidden
            defects.append(("crash", older, newer, repr(e)))
            continue
        counts[result.verdict] += 1
        if result.verdict == "proven":
            for v in PROBES:
                record = {"f": v}
                if valid(older, record) and not valid(newer, record):
                    defects.append(("FALSE PROOF", older, newer, record))
                    break
        elif result.verdict == "falsified":
            w = result.witness
            if not valid(older, w) or valid(newer, w):
                defects.append(("UNCONFIRMED WITNESS", older, newer, w))
    return defects, counts


@pytest.mark.parametrize("eco", ["jsonschema", "pydantic"])
def test_union_shapes_agree_with_the_library(eco):
    defects, counts = run(eco, PAIRS, SEED)
    print(eco, counts)
    assert not defects, "\n".join(map(str, defects[:8])) + f"\n({len(defects)} total)"
