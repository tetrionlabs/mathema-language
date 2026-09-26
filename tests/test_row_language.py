# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A row language over every ecosystem the package reads: it conforms
to mathema's protocol, every hazard is a member, two hundred samples
are members by the ecosystem's own validator, `outside` never is,
shrinking stays inside, `fields()` states the one-deep bounds, a
finite schema enumerates, and a schema nothing satisfies says so
with the counts."""
import random
import sys
from dataclasses import dataclass, field
from typing import Annotated, Literal, Optional, TypedDict

import pytest

from mathema_language.schema import NoMember, RowLanguage
from mathema_language.schema.adaptors import adapt_row

pytest.importorskip("mathema")
from mathema.languages import language_problems  # noqa: E402


class Ge:
    def __init__(self, ge):
        self.ge = ge


class Le:
    def __init__(self, le):
        self.le = le


class MaxLen:
    def __init__(self, max_length):
        self.max_length = max_length


@dataclass
class Order:
    id: int
    qty: Annotated[int, Ge(1), Le(10)]
    price: Annotated[float, Ge(0.0)]
    sku: Annotated[str, MaxLen(8)]
    kind: Literal["web", "shop"]
    note: str | None = None
    tags: list[str] = field(default_factory=list)


class OrderDict(TypedDict, total=True):
    id: int
    qty: Annotated[int, Ge(1), Le(10)]
    price: Annotated[float, Ge(0.0)]
    sku: Annotated[str, MaxLen(8)]
    kind: Literal["web", "shop"]
    note: Optional[str]  # noqa: UP045, the old spelling reads the same


def _shapes():
    out = [("dataclass", Order), ("typeddict", OrderDict)]
    if "pydantic" in sys.modules or _importable("pydantic"):
        from tests._pydantic_shapes import OrderModel
        out.append(("pydantic", OrderModel))
    if _importable("jsonschema"):
        from tests._jsonschema_shapes import ORDER_SCHEMA
        out.append(("jsonschema", ORDER_SCHEMA))
    return out


def _importable(name):
    import importlib.util
    return importlib.util.find_spec(name) is not None


try:
    SHAPES = _shapes()
except ImportError:
    SHAPES = [("dataclass", Order), ("typeddict", OrderDict)]


@pytest.fixture(params=SHAPES, ids=[name for name, _ in SHAPES])
def language(request):
    name, shape = request.param
    lang = adapt_row(shape)
    assert isinstance(lang, RowLanguage), (name, lang)
    return lang


def test_the_language_conforms(language):
    assert language_problems(language) == []
    assert language.kind == "row" and language.level == "schema"
    assert language.render(True) == f"L[{language.name}]"


def test_every_hazard_is_a_member(language):
    hazards = language.hazards()
    assert len(hazards) >= 20
    for h in hazards:
        assert language.contains(h.value), (h.note, language.explain(h.value))
    kinds = {h.kind for h in hazards}
    assert {"extremity", "null", "empty", "control", "shape"} <= kinds


def test_two_hundred_samples_are_members_by_the_ecosystem_s_validator(language):
    rng = random.Random(7)
    for _ in range(200):
        row = language.sample(rng)
        assert language.ecosystem.validate_row(language.schema, row) == [], row
    assert language.accepted >= 200


def test_outside_is_never_a_member(language):
    rng = random.Random(3)
    for _ in range(40):
        bad = language.outside(rng)
        assert bad is not None
        assert not language.contains(bad), bad
        assert language.explain(bad)


def test_shrinking_stays_inside(language):
    rng = random.Random(11)
    row = language.sample(rng)
    smaller = list(language.shrink(row))
    assert smaller, row
    for candidate in smaller:
        assert language.contains(candidate)


def test_fields_state_the_one_deep_bounds(language):
    bounds = language.fields()
    assert bounds["qty"] == (1.0, 10.0)
    assert bounds["price"] == "R" or bounds["price"] == (0.0, 1e6) or isinstance(bounds["price"], tuple)
    assert bounds["id"] == "Z"
    assert str(bounds["sku"]) in ("L[unicode]", "LanguageRef(name='unicode')")


def test_a_finite_schema_enumerates():
    @dataclass
    class Flags:
        on: bool
        mode: Literal["a", "b", "c"]

    lang = adapt_row(Flags)
    members = lang.members(10)
    assert members is not None and len(members) == 6
    assert lang.members(5) is None


def test_a_schema_nothing_satisfies_says_so_with_the_counts():
    @dataclass
    class Impossible:
        n: Annotated[int, Ge(1), Le(10)]

    lang = adapt_row(Impossible)
    lang.schema = type(lang.schema)(lang.schema.name, lang.schema.fields,
                                    checks=(lambda row: row.n > 10,))
    with pytest.raises(NoMember, match="no member found in 50 draws"):
        lang.sample(random.Random(0))


def test_a_regex_on_a_stdlib_schema_is_refused_at_adaptation():
    class Pattern:
        def __init__(self, pattern):
            self.pattern = pattern

    @dataclass
    class Coded:
        code: Annotated[str, Pattern("[A-Z]{3}")]

    with pytest.raises(ValueError, match="no validator to hold it to"):
        adapt_row(Coded)


def test_a_regex_field_generates_matching_members():
    from mathema_language.schema.adaptors.jsonschema import adapt as adapt_json

    lang = adapt_json({"type": "object", "title": "Coded",
                       "properties": {"code": {"type": "string", "pattern": "^[A-Z]{3}-[0-9]{2,4}$"}},
                       "required": ["code"], "additionalProperties": False})
    rng = random.Random(4)
    for _ in range(50):
        row = lang.sample(rng)
        assert lang.contains(row), row
    assert lang.accepted == 50 and lang.rejected == 0


def test_the_pydantic_adaptor_answers_not_mine_without_importing_pydantic():
    import subprocess
    import sys as _sys
    code = ("import sys; from mathema_language.schema.adaptors.pydantic import adapt; "
            "print(adapt(int), 'pydantic' in sys.modules)")
    out = subprocess.run([_sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "None False", out.stdout
