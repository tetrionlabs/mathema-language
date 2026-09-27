# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The dataclass adaptor: conforms by the harness, answers not mine for
anything that is not a dataclass class, checks members with the neutral
checker, and refuses a regular expression it has no validator for."""
from dataclasses import dataclass
from typing import Annotated

import pytest
from annotated_types import Ge, Le, MaxLen

from mathema_language.conformance import assert_row_adaptor, not_mine_problems
from mathema_language.schema.adaptors.dataclass import adapt


@dataclass
class Line:
    sku: Annotated[str, MaxLen(8)]
    qty: Annotated[int, Ge(1), Le(10)]
    price: Annotated[float, Ge(0.0)]
    note: str | None = None


def test_conforms():
    language = assert_row_adaptor(Line, adapt=adapt)
    assert type(language.ecosystem).__name__ == "AttributeEcosystem"


def test_not_mine():
    assert not_mine_problems(adapt) == []


def test_an_instance_is_not_a_schema():
    assert adapt(Line("a", 1, 0.0)) is None


def test_the_neutral_checker_explains_a_bound():
    language = adapt(Line)
    problems = language.explain(Line("abc", 0, 1.0))
    assert [(p.path, p.predicate) for p in problems] == [(".qty", ">= 1")]


def test_a_regular_expression_is_refused():
    class Pattern:
        def __init__(self, pattern):
            self.pattern = pattern

    @dataclass
    class Coded:
        code: Annotated[str, Pattern("^[A-Z]+$")]

    with pytest.raises(ValueError, match="regular expression"):
        adapt(Coded)
