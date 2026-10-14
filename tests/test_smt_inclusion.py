# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Schema inclusion decided by z3. A widened schema is proven to admit
every record the original did; a narrowed one, one with a new required
field, or one with a pattern the original lacks is falsified with a
record both validations confirm; a custom validator or a JSON Schema
keyword the adaptor does not read is unknown, named. The encoding is
held to the two conditions a proof rests on, over drawn members and
values just outside: every member of a language satisfies its encoding
as the older schema, and every value its encoding as the newer schema
admits is a member."""
import decimal
import random
from dataclasses import dataclass
from typing import Literal

import pytest

z3 = pytest.importorskip("z3")
pytest.importorskip("pydantic")
pytest.importorskip("jsonschema")

from pydantic import BaseModel, Field, field_validator  # noqa: E402

from mathema_language import smt  # noqa: E402
from mathema_language.schema.adaptors import adapt_row  # noqa: E402


class V1(BaseModel):
    sku: str = Field(min_length=1, max_length=12)
    qty: int = Field(ge=1, le=10)
    price: float = Field(ge=0, le=1000)


class Widened(BaseModel):
    sku: str = Field(min_length=1, max_length=20)
    qty: int = Field(ge=1, le=100)
    price: float = Field(ge=0, le=5000)


class Narrowed(BaseModel):
    sku: str = Field(min_length=1, max_length=12)
    qty: int = Field(ge=1, le=5)
    price: float = Field(ge=0, le=1000)


class NewRequired(BaseModel):
    sku: str = Field(min_length=1, max_length=12)
    qty: int = Field(ge=1, le=10)
    price: float = Field(ge=0, le=1000)
    currency: str


class Pattern(BaseModel):
    sku: str = Field(pattern=r"^[A-Z]{3}-[0-9]{4}$")
    qty: int = Field(ge=1, le=10)
    price: float = Field(ge=0, le=1000)


class Validated(BaseModel):
    sku: str
    qty: int
    price: float

    @field_validator("qty")
    @classmethod
    def unchanged(cls, v: int) -> int:
        return v


class Rich(BaseModel):
    rate: decimal.Decimal = Field(max_digits=5, decimal_places=2, gt=0)
    step: int = Field(multiple_of=5, gt=-50, lt=50)
    kind: Literal["a", "b"] = "a"
    note: str | None = None
    ratio: float = Field(gt=0.0, lt=1.0)


@dataclass
class Line:
    sku: str
    qty: int
    note: str | None = None


ORDER_V1 = {"type": "object", "required": ["sku", "qty"],
            "properties": {"sku": {"type": "string", "minLength": 1},
                           "qty": {"type": "integer", "minimum": 1, "maximum": 10}}}
ORDER_V2 = {"type": "object", "required": ["sku", "qty", "note"],
            "properties": {"sku": {"type": "string", "minLength": 1},
                           "qty": {"type": "integer", "minimum": 1, "maximum": 10},
                           "note": {"type": "string"}}}
ORDER_FORMAT = {"type": "object", "required": ["sku", "qty"],
                "properties": {"sku": {"type": "string", "format": "uuid"},
                               "qty": {"type": "integer"}}}


@pytest.mark.parametrize("older, newer, verdict", [
    (V1, Widened, "proven"),
    (V1, V1, "proven"),
    (Pattern, V1, "proven"),
    (V1, Narrowed, "falsified"),
    (V1, NewRequired, "falsified"),
    (V1, Pattern, "falsified"),
    (ORDER_V1, ORDER_V1, "proven"),
    (ORDER_V1, ORDER_V2, "falsified"),
], ids=lambda v: getattr(v, "__name__", None) or (v if isinstance(v, str) else "schema"))
def test_inclusion_between_versions(older, newer, verdict):
    result = smt._schema_inclusion(older, newer)
    assert result.verdict == verdict, str(result)
    if verdict == "falsified":
        assert smt._admits(adapt_row(older), result.witness)
        assert not smt._admits(adapt_row(newer), result.witness)


def test_a_witness_leaves_out_what_the_older_schema_does_not_have():
    assert smt._schema_inclusion(V1, NewRequired).witness == {"sku": "A", "qty": 1, "price": 0.0}
    assert "note" not in smt._schema_inclusion(ORDER_V1, ORDER_V2).witness


@pytest.mark.parametrize("older, newer, named", [
    (V1, Validated, "a custom validator"),
    (ORDER_V1, ORDER_FORMAT, "'format'"),
])
def test_what_the_encoding_does_not_read_is_unknown_and_named(older, newer, named):
    result = smt._schema_inclusion(older, newer)
    assert result.verdict == "unknown" and named in result.reason


def _satisfies(language, values, side):
    """Whether `values` satisfies the language's encoding on `side`."""
    enc = smt.MembershipEncoding(z3)
    names = [f.name for f in language.schema.fields]
    formula = enc.row(language.schema, names, side, smt._SUPPORTED[language.ecosystem.name])
    solver = z3.Solver()
    solver.add(formula)
    for name in names:
        solver.add(enc.var(name) == (enc.const(values[name]) if name in values else enc.V.absent))
    return solver.check() == z3.sat


def _past_z3(values):
    """Text past z3's characters: such a record reads, to the encoding, as
    one with that character replaced (see the smt module), so it is not
    evaluated directly."""
    return any(isinstance(v, str) and any(ord(c) > smt._Z3_MAX_CHAR for c in v)
               for v in values.values())


def _values(language, row):
    out = {}
    for f in language.schema.fields:
        if isinstance(row, dict):
            if f.name in row:
                out[f.name] = row[f.name]
        elif hasattr(row, f.name):
            out[f.name] = getattr(row, f.name)
    return out


@pytest.mark.parametrize("schema", [V1, Pattern, Rich, Line, ORDER_V1, ORDER_V2],
                         ids=["pydantic", "pattern", "rich", "dataclass", "json-v1", "json-v2"])
def test_the_encoding_never_admits_less_than_older_or_more_than_newer(schema):
    language = adapt_row(schema)
    rng = random.Random(7)
    members = [language.sample(rng) for _ in range(60)]
    members += [h.value for h in language.hazards()[:30]]
    for row in members:
        values = _values(language, row)
        if _past_z3(values):
            continue
        try:
            encodable = all(smt.MembershipEncoding(z3).const(v) is not None for v in values.values())
        except smt.Untranslated:
            continue
        if encodable:
            assert _satisfies(language, values, "older"), values
    for _ in range(60):
        row = language.outside(rng)
        if row is None:
            continue
        values = _values(language, row)
        if _past_z3(values):
            continue
        try:
            newer = _satisfies(language, values, "newer")
        except smt.Untranslated:
            continue
        if newer:
            assert smt._admits(language, values), values


PATTERNS = [r"^\w{2,4}-\d+$", r"[^x]y", r"^(ab|c)+\.?$", r"^[A-Z]{3}-[0-9]{4}$", r"colou?r"]
TEXTS = ["ab-12", "é1-7", "xy", "ay", "zzay\n", "abcab", "abc.", "ABC-1234", "ABC-1234\n",
         "color", "the colour", "", "a", "ab-", "\u00e9\u00e9-\u0661"]


@pytest.mark.parametrize("pattern", PATTERNS)
def test_a_pattern_reads_at_least_as_search_on_the_older_side_and_at_most_as_a_full_match_on_the_newer(pattern):
    import re
    for side in ("older", "newer"):
        enc = smt.MembershipEncoding(z3)
        regex = enc._regex(pattern, side)
        for text in TEXTS:
            solver = z3.Solver()
            solver.add(z3.InRe(z3.StringVal(text), regex))
            inside = solver.check() == z3.sat
            if side == "older" and re.search(pattern, text):
                assert inside, (pattern, text)
            if side == "newer" and inside:
                assert re.fullmatch(pattern, text), (pattern, text)


def test_a_decimal_limit_the_neutral_model_cannot_carry_is_unknown():
    class Digits(BaseModel):
        rate: decimal.Decimal = Field(max_digits=5)

    result = smt._schema_inclusion(Digits, Digits)
    assert result.verdict == "unknown" and "decimal digits on .rate" in result.reason
