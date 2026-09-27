# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The pydantic adaptor: conforms by the harness, answers not mine for
anything that is not a model class, and membership is the model's own
`model_validate`, so a non-member is explained in pydantic's words."""
import pytest

pydantic = pytest.importorskip("pydantic")

from mathema_language.conformance import (  # noqa: E402
    assert_row_adaptor,
    not_mine_problems,
)
from mathema_language.schema.adaptors.pydantic import adapt  # noqa: E402
from tests._pydantic_shapes import OrderModel  # noqa: E402


def test_conforms():
    language = assert_row_adaptor(OrderModel, adapt=adapt)
    assert type(language.ecosystem).__name__ == "PydanticEcosystem"


def test_not_mine():
    assert not_mine_problems(adapt) == []


def test_a_non_member_is_explained_in_pydantic_s_words():
    language = adapt(OrderModel)
    row = OrderModel.model_construct(id=1, qty=0, price=-1.0, sku="abc", kind="web", note=None)
    assert [(p.path, p.predicate) for p in language.explain(row)] == [
        (".qty", "Input should be greater than or equal to 1"),
        (".price", "Input should be greater than or equal to 0"),
    ]


def test_extra_forbid_is_the_exact_column_policy():
    assert adapt(OrderModel).schema.column_policy == "exact"
