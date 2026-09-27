# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The TypedDict adaptor: conforms by the harness, answers not mine for
anything that is not a TypedDict, and members are plain dicts checked
by the neutral checker, a missing required key included."""
from typing import Annotated, TypedDict

from annotated_types import Ge, Le, MaxLen

from mathema_language.conformance import assert_row_adaptor, not_mine_problems
from mathema_language.schema.adaptors.typeddict import adapt


class LineDict(TypedDict):
    sku: Annotated[str, MaxLen(8)]
    qty: Annotated[int, Ge(1), Le(10)]
    price: Annotated[float, Ge(0.0)]


def test_conforms():
    language = assert_row_adaptor(LineDict, adapt=adapt)
    assert type(language.ecosystem).__name__ == "PlainEcosystem"


def test_not_mine():
    assert not_mine_problems(adapt) == []


def test_a_missing_key_and_a_bound_are_explained():
    language = adapt(LineDict)
    problems = language.explain({"sku": "abcdefghij", "qty": 3})
    assert [(p.path, p.predicate) for p in problems] == [(".sku", "len <= 8"), (".price", "present")]
