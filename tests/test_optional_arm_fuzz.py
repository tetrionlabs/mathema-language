# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
# ruff: noqa: UP045, UP007, F401
"""Seeded fuzz of constraint positions against each library's own validation.

A `proven` verdict must not be contradicted by a probed value that the older side admits and the
newer refuses (pydantic lax and strict, jsonschema, the adaptor's membership for dataclasses and
TypedDicts); a `falsified` witness must be admitted by older and refused by newer under the library.
Default budget is small; REVIEW_FUZZ_PAIRS sets the pair count per ecosystem, REVIEW_FUZZ_SEED the seed.
Set REVIEW_FUZZ_DUMP=path to write every verdict as JSON (to diff two checkouts).
"""
import json
import os
import random
from dataclasses import make_dataclass
from typing import Annotated, Optional, TypedDict, Union

import pytest

pytest.importorskip("z3")
pytest.importorskip("pydantic")
pytest.importorskip("jsonschema")

import jsonschema  # noqa: E402
from annotated_types import Ge, Le, MaxLen, MinLen  # noqa: E402
from pydantic import Field, ValidationError, conint, constr, create_model  # noqa: E402

from mathema_language import smt  # noqa: E402
from mathema_language.schema.adaptors import adapt_row  # noqa: E402

PAIRS = int(os.environ.get("REVIEW_FUZZ_PAIRS", "25"))
SEED = int(os.environ.get("REVIEW_FUZZ_SEED", "5301"))
INT_LO, INT_HI = [None, 0, 1, 3], [None, 3, 5, 8]
STR_LO, STR_HI = [None, 0, 1, 2], [None, 3, 5]


def _kw(kind, lo, hi):
    if kind is int:
        return {k: v for k, v in (("ge", lo), ("le", hi)) if v is not None}
    return {k: v for k, v in (("min_length", lo), ("max_length", hi)) if v is not None}


def _marks(kind, lo, hi):
    if kind is int:
        return [m for m in (Ge(lo) if lo is not None else None, Le(hi) if hi is not None else None) if m]
    return [m for m in (MinLen(lo) if lo is not None else None, MaxLen(hi) if hi is not None else None) if m]


def pyd_annotation(form, kind, lo, hi, hi2):
    T = kind
    kw = _kw(kind, lo, hi)
    if form == "optional":
        return Optional[Annotated[T, Field(**kw)]]
    if form == "pipe":
        return Annotated[T, Field(**kw)] | None
    if form == "outer":
        return Annotated[Optional[T], Field(**kw)]
    if form == "nested":
        return Annotated[Annotated[T, Field(**_kw(kind, lo, None))], Field(**_kw(kind, None, hi))]
    if form == "nested_conflict":
        return Annotated[Annotated[T, Field(**_kw(kind, None, hi2))], Field(**_kw(kind, None, hi))]
    if form == "plain":
        return Annotated[T, Field(**kw)]
    if form == "meta_only":
        return Annotated[Optional[T], Field(description="d", default=None, **kw)]
    if form == "atypes_mixed":
        return Optional[Annotated[(T, *_marks(kind, lo, None), Field(**_kw(kind, None, hi)))]]
    if form == "constrained":
        if kind is int:
            return Optional[conint(**kw)]
        return Optional[constr(**kw)]
    if form == "list_items":
        return list[Optional[Annotated[T, Field(**kw)]]]
    if form == "optional_list":
        return Optional[list[Annotated[T, Field(**kw)]]]
    if form == "union2":
        return Union[Annotated[int, Field(**_kw(int, lo, hi))],
                     Annotated[str, Field(**_kw(str, None, hi2))]]
    raise ValueError(form)


PYD_FORMS = ["optional", "pipe", "outer", "nested", "nested_conflict", "plain", "meta_only",
             "atypes_mixed", "constrained", "list_items", "optional_list", "union2"]


class _Ann:
    """`Annotated[(T, *marks)]`, or `T` alone when there are no marks."""

    def __getitem__(self, args):
        T, *marks = args
        return Annotated[(T, *marks)] if marks else T


_ann = _Ann()


def dc_annotation(form, kind, lo, hi, hi2):
    T = kind
    ms = _marks(kind, lo, hi)
    if form == "optional":
        return Optional[_ann[(T, *ms)]]
    if form == "pipe":
        return _ann[(T, *ms)] | None
    if form == "outer":
        return _ann[(Optional[T], *ms)]
    if form == "nested":
        return _ann[(_ann[(T, *_marks(kind, lo, None))], *_marks(kind, None, hi))]
    if form == "nested_conflict":
        return _ann[(_ann[(T, *_marks(kind, None, hi2))], *_marks(kind, None, hi))]
    if form == "plain":
        return _ann[(T, *ms)]
    if form == "list_items":
        return list[Optional[_ann[(T, *ms)]]]
    if form == "union2":
        return Union[_ann[(int, *_marks(int, lo, hi))], _ann[(str, *_marks(str, None, hi2))]]
    raise ValueError(form)


DC_FORMS = ["optional", "pipe", "outer", "nested", "nested_conflict", "plain", "list_items", "union2"]


def js_property(form, kind, lo, hi, hi2):
    t = "integer" if kind is int else "string"
    lo_k, hi_k = ("minimum", "maximum") if kind is int else ("minLength", "maxLength")

    def bounds(low, h):
        return {k: v for k, v in ((lo_k, low), (hi_k, h)) if v is not None}
    base = {"type": t, **bounds(lo, hi)}
    null = {"type": "null"}
    if form == "plain":
        return base
    if form == "anyof_arm":
        return {"anyOf": [base, null]}
    if form == "oneof_arm":
        return {"oneOf": [null, base]}
    if form == "outer_and_arm":
        return {**bounds(lo, hi), "anyOf": [{"type": t, **bounds(None, hi2)}, null]}
    if form == "outer_only":
        return {**bounds(lo, hi), "anyOf": [{"type": t}, null]}
    if form == "conflict":
        return {**bounds(hi2, hi), "anyOf": [{"type": t, **bounds(lo, hi2)}, null]}
    if form == "two_types":
        return {"anyOf": [{"type": "integer", **bounds(lo, hi)} if kind is int else {"type": "integer"},
                          {"type": "string", **({"maxLength": hi2} if hi2 else {})}]}
    if form == "nested_anyof":
        return {"anyOf": [{"anyOf": [base, {"type": "boolean"}]}, null]}
    if form == "nested_anyof_one":
        return {"anyOf": [{"anyOf": [base, null]}, null]}
    raise ValueError(form)


JS_FORMS = ["plain", "anyof_arm", "oneof_arm", "outer_and_arm", "outer_only", "conflict",
            "two_types", "nested_anyof", "nested_anyof_one"]


def probes(spec_list):
    """Values near every bound of every spec, for int and str, plus None and a list shape."""
    ints, lens = {-1, 0, 1, 2, 4, 6, 9, 100}, {0, 1, 2, 4, 6, 10}
    for (_, _kind, lo, hi, hi2) in spec_list:
        for b in (lo, hi, hi2):
            if b is not None:
                (ints if True else lens).update({b - 1, b, b + 1})
                lens.update({max(b - 1, 0), b, b + 1})
    vals = [None, True, 1.5, "x"] + sorted(ints) + ["a" * n for n in sorted(lens)]
    return vals


def draw_spec(rng, forms):
    form = rng.choice(forms)
    kind = rng.choice([int, str])
    if kind is int:
        lo, hi = rng.choice(INT_LO), rng.choice(INT_HI)
    else:
        lo, hi = rng.choice(STR_LO), rng.choice(STR_HI)
    hi2 = rng.choice([3, 5, 8]) if kind is int else rng.choice([3, 5])
    if form == "union2":
        kind = int
        lo, hi = rng.choice(INT_LO), rng.choice(INT_HI)
        hi2 = rng.choice([3, 5])
    return (form, kind, lo, hi, hi2)


def _wrap(form, v):
    if form in ("list_items", "optional_list"):
        return [v]
    return v


def build(eco, specs):
    if eco == "pydantic":
        return create_model("M", **{f"f{i}": (pyd_annotation(*s[:1], *s[1:]), ...) for i, s in enumerate(specs)})
    if eco == "dataclass":
        return make_dataclass("D", [(f"f{i}", dc_annotation(*s)) for i, s in enumerate(specs)])
    if eco == "typeddict":
        return TypedDict("T", {f"f{i}": dc_annotation(*s) for i, s in enumerate(specs)})
    return {"type": "object", "required": [f"f{i}" for i in range(len(specs))],
            "properties": {f"f{i}": js_property(*s) for i, s in enumerate(specs)}}


def oracles(eco, model):
    """Library validators: name -> callable(dict) -> bool."""
    if eco == "pydantic":
        def lax(d):
            try:
                model.model_validate(d)
                return True
            except ValidationError:
                return False

        def strict(d):
            try:
                model.model_validate(d, strict=True)
                return True
            except ValidationError:
                return False
        return {"lax": lax, "strict": strict}
    if eco == "jsonschema":
        def js(d):
            try:
                jsonschema.validate(d, model)
                return True
            except jsonschema.ValidationError:
                return False
        return {"jsonschema": js}
    lang = adapt_row(model)
    return {"membership": lambda d: smt._admits(lang, d)}


FORMS = {"pydantic": PYD_FORMS, "dataclass": DC_FORMS, "typeddict": DC_FORMS, "jsonschema": JS_FORMS}


def run(eco, pairs, seed, dump=None):
    rng = random.Random(f"{seed}-{eco}")
    defects, counts = [], {"proven": 0, "falsified": 0, "unknown": 0, "probes": 0}
    for _n in range(pairs):
        nf = 1
        old_s = [draw_spec(rng, FORMS[eco]) for _ in range(nf)]
        # newer shares each field's form and kind half the time, so narrowing is exercised
        new_s = [(s[0], s[1], *(rng.choice([INT_LO, STR_LO][s[1] is str]), rng.choice([INT_HI, STR_HI][s[1] is str])), s[4])
                 if rng.random() < 0.7 else draw_spec(rng, FORMS[eco]) for s in old_s]
        try:
            older, newer = build(eco, old_s), build(eco, new_s)
            res = smt._schema_inclusion(older, newer)
        except Exception as e:  # report, do not hide
            defects.append(("crash", old_s, new_s, repr(e)))
            continue
        counts[res.verdict] += 1
        if dump is not None:
            dump.append({"eco": eco, "old": [str(x) for x in old_s], "new": [str(x) for x in new_s],
                         "verdict": res.verdict})
        po, pn = oracles(eco, older), oracles(eco, newer)
        if res.verdict == "proven":
            vals = probes(old_s + new_s)
            for v in vals:
                for _ctx in ([v], ):
                    d = {"f0": _wrap(old_s[0][0], v)}
                    for name in po:
                        counts["probes"] += 1
                        if po[name](d) and not pn[name](d):
                            defects.append(("FALSE PROOF", name, old_s, new_s, d))
                    if "membership" in po or "jsonschema" in po:
                        continue
            for name in po:  # absent / null handled via vals; absent field:
                if po[name]({}) and not pn[name]({}):
                    defects.append(("FALSE PROOF (absent)", name, old_s, new_s, {}))
        elif res.verdict == "falsified":
            w = res.witness
            for name in po:
                if not po[name](w) or pn[name](w):
                    defects.append(("UNCONFIRMED WITNESS", name, old_s, new_s, w))
    return defects, counts


@pytest.mark.parametrize("eco", ["pydantic", "dataclass", "typeddict", "jsonschema"])
def test_fuzz_proven_and_falsified_agree_with_the_library(eco):
    dump = []
    defects, counts = run(eco, PAIRS, SEED, dump)
    path = os.environ.get("REVIEW_FUZZ_DUMP")
    if path:
        with open(f"{path}.{eco}.json", "w") as fh:
            json.dump(dump, fh)
    print(eco, counts)
    assert not defects, "\n".join(map(str, defects[:10])) + f"\n({len(defects)} total)"
