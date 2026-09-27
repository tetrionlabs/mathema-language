# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The Django adaptor: conforms by the harness, answers not mine for
anything that is not a model class, and leaves what the neutral model
cannot read to `full_clean`: a custom validator's message is the
explanation."""
import pytest

pytest.importorskip("django")

from mathema_language.conformance import (  # noqa: E402
    assert_row_adaptor,
    not_mine_problems,
)
from mathema_language.schema.adaptors.django import adapt  # noqa: E402
from tests import _django_shapes as shapes  # noqa: E402


def test_conforms():
    language = assert_row_adaptor(shapes.OrderModelDj, adapt=adapt)
    assert type(language.ecosystem).__name__ == "DjangoEcosystem"


def test_not_mine():
    assert not_mine_problems(adapt) == []


def test_a_custom_validator_is_full_clean_s():
    language = adapt(shapes.CodedDj)
    assert language.contains(shapes.CodedDj(code="ABC"))
    assert [(p.path, p.predicate) for p in language.explain(shapes.CodedDj(code="abc"))] == [
        (".code", "code must be upper case")]
