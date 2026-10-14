# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A record language from a library with a validator of its own declares
that library's validation error as its refusal: a function over pydantic
records refuses an invalid one with pydantic's ValidationError, so
`excluded_outside_domain` holds for a function that validates through
the model and is falsified for one that refuses with an error of its own
or lets the record through. A schema with no validator of its own (a
dataclass) declares none, and any raise refuses."""
from dataclasses import dataclass

import mathema.languages as languages
import pytest

pydantic = pytest.importorskip("pydantic")

from pydantic import BaseModel, Field  # noqa: E402

from mathema_language.schema.adaptors.dataclass import adapt as adapt_dataclass  # noqa: E402
from mathema_language.schema.adaptors.pydantic import adapt as adapt_pydantic  # noqa: E402


class Item(BaseModel):
    sku: str = Field(min_length=1)
    qty: int = Field(ge=1, le=10)


def revalidated(item: Item) -> int:
    """Validates through the model, as a handler receiving a record built
    without validation should."""
    return Item.model_validate(item.model_dump()).qty


def own_error(item: Item) -> int:
    if not 1 <= item.qty <= 10 or not item.sku:
        raise ValueError("bad item")
    return item.qty


def trusting(item: Item) -> int:
    return item.qty


@pytest.mark.parametrize("fn, verdict", [(revalidated, "holds"), (own_error, "falsified"),
                                         (trusting, "falsified")], ids=lambda v: getattr(v, "__name__", v))
def test_a_pydantic_record_is_refused_with_pydantic_s_own_error(fn, verdict):
    from mathema.conjecture import check_conjectures, claim
    language = adapt_pydantic(Item)
    assert language.refusal is not None and language.refusal.text == "pydantic ValidationError"
    languages.register_language("refusal_items", language)
    (p,) = check_conjectures(fn, [claim("for item in L[refusal_items], excluded_outside_domain(item)")])
    assert p.verdict == verdict, (p.note, p.counterexample)


@dataclass
class Plain:
    qty: int


def test_a_schema_with_no_validator_of_its_own_declares_no_refusal():
    assert adapt_dataclass(Plain).refusal is None
