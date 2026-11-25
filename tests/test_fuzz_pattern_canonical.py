# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A picture's canonical text reads back to itself and to the same
language, on generated pictures with bindings over both bases, drawn
from atoms that hold every escape and quoting form; and an inclusion
between records whose fields carry a picture pattern is never reported
proven where a member of the one is not in the other, nor falsified
where it holds, whichever adaptor reads the records. Seeded; a small
budget by default, the full one under `heavy`."""
import json
import random
import typing
from dataclasses import dataclass

import pytest

from mathema_language.text import _algebra
from mathema_language.text.pattern import Pattern, PatternError
from tests import _fuzz
from tests._pattern_oracle import reads

SEED = 3
ATOMS = ["A", "a", "9", "X", "W", "5", "-", " ", "'ab'", "'K'", "'-.'", "\\[", "\\]", "\\'", "\\K", "\\9", "\\a",
         "\\A", "'''", "''''", "'a''b'", ".", "_", "\\\\", "'cd'", "\\{", "\\}", "'{'", "'['", "'9'", "'A'", "'x'",
         "'X'", "'\\'", "\\-", "'é'", "\\é", "'a b'", "'''a'", "'a'''"]


def _picture(rng: random.Random, depth: int = 0) -> str:
    out = ""
    for _ in range(rng.randint(1, 4)):
        atom = "[" + _picture(rng, depth + 1) + "]" if depth < 2 and rng.random() < 0.2 else rng.choice(ATOMS)
        roll = rng.random()
        if roll < 0.25:
            atom += f"{{{rng.randint(1, 3)}}}"
        elif roll < 0.35:
            lo = rng.randint(0, 2)
            atom += f"{{{lo},{lo + rng.randint(0 if lo else 1, 2)}}}"
        elif roll < 0.4:
            atom += f"{{{rng.randint(0, 2)}+}}"
        out += atom
    return out


def _key(pattern: Pattern) -> str:
    term = pattern.term()
    low = term.get("language") or term["at_least"]
    high = term.get("at_most") or term.get("language")
    return json.dumps(_algebra.canonical(low), sort_keys=True) + json.dumps(_algebra.canonical(high), sort_keys=True)


def _check(n: int) -> int:
    rng = random.Random(SEED)
    checked = 0
    for _ in range(n):
        written, base = _picture(rng), rng.choice(["ascii", "unicode"])
        bindings = {}
        if "W" in written:
            bindings["W"] = rng.choice(["lower", "hexdigit", '"a" + "\'"', 'upper + "-"'])
        if "5" in written:
            bindings["5"] = rng.choice(["digit", '"5"'])
        if rng.random() < 0.2 and "A" in written:
            bindings["A"] = "upper"
        if rng.random() < 0.2 and "9" in written:
            bindings["9"] = '"0" + "1"'
        try:
            pattern = Pattern(written, base, bindings)
        except (PatternError, ValueError):
            continue
        checked += 1
        again = Pattern(pattern.canonical, base, {k: v.text for k, v in pattern.bindings})
        assert again.canonical == pattern.canonical, (written, pattern.canonical, again.canonical)
        if _key(again) != _key(pattern):
            texts = set(pattern.members()) | set(again.members()) | {pattern.draw(rng) for _ in range(10)}
            assert [t for t in texts if reads(pattern, t) != reads(again, t)] == [], (written, pattern.canonical)
    return checked


def test_generated_pictures_read_back_from_their_canonical_text():
    checked = _check(400)
    _fuzz.report("pattern canonical text", SEED, pictures=checked)
    assert checked >= 200


@_fuzz.heavy
def test_generated_pictures_read_back_from_their_canonical_text_at_full_size():
    checked = _check(5000)
    _fuzz.report("pattern canonical text, full", SEED, pictures=checked)


POSTCODE = Pattern("AA99", "ascii")


@dataclass
class Plain:
    a: str


@dataclass
class Marked:
    a: typing.Annotated[str, POSTCODE]


@dataclass
class OptionalMarked:
    a: typing.Optional[typing.Annotated[str, POSTCODE]]  # noqa: UP045


@dataclass
class ListPlain:
    a: list[str]


@dataclass
class ListMarked:
    a: list[typing.Annotated[str, POSTCODE]]


@dataclass
class InnerMarked:
    a: typing.Annotated[str, POSTCODE]


@dataclass
class InnerPlain:
    a: str


@dataclass
class NestMarked:
    x: InnerMarked


@dataclass
class NestPlain:
    x: InnerPlain


class TypedPlain(typing.TypedDict):
    a: str


class TypedMarked(typing.TypedDict):
    a: typing.Annotated[str, POSTCODE]


def _pairs():
    pydantic = pytest.importorskip("pydantic")

    class ModelPlain(pydantic.BaseModel):
        a: str

    class ModelMarked(pydantic.BaseModel):
        a: typing.Annotated[str, POSTCODE]

    class ModelMarkedRe(pydantic.BaseModel):
        model_config = {"regex_engine": "python-re"}
        a: typing.Annotated[str, POSTCODE]

    wider = [(Plain, Marked), (Plain, OptionalMarked), (ListPlain, ListMarked), (NestPlain, NestMarked),
             (TypedPlain, TypedMarked), (ModelPlain, ModelMarked), (ModelPlain, ModelMarkedRe),
             (Plain, ModelMarked), (ModelPlain, Marked)]
    within = [(Marked, Plain), (Marked, Marked), (ModelMarked, ModelMarked)]
    return wider, within


def test_an_inclusion_over_picture_pattern_fields_is_never_decided_wrongly():
    pytest.importorskip("z3")
    from mathema_language import smt
    wider, within = _pairs()
    for older, newer in wider:
        found = smt._schema_inclusion(older, newer, timeout_ms=3000)
        assert found.verdict != "proven", (older.__name__, newer.__name__, found.reason)
    for older, newer in within:
        found = smt._schema_inclusion(older, newer, timeout_ms=3000)
        assert found.verdict != "falsified", (older.__name__, newer.__name__, found.reason, found.witness)
    _fuzz.report("pattern field inclusions", 0, wider=len(wider), within=len(within))
