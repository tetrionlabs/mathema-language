# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
# ruff: noqa: UP045, UP007
"""A bound on the items of a list in a dataclass, TypedDict or pydantic model is never proven
away; the same list type on both sides stays proven."""
from dataclasses import dataclass
from typing import Annotated, Optional, TypedDict

import pytest

pytest.importorskip("z3")
pytest.importorskip("pydantic")

from annotated_types import Ge  # noqa: E402
from pydantic import create_model  # noqa: E402

from mathema_language import smt  # noqa: E402


def _dataclass(t):
    @dataclass
    class Rec:
        f: t
    return Rec


def _typeddict(t):
    class Rec(TypedDict):
        f: t
    return Rec


def _pydantic(t):
    return create_model("Rec", f=(t, ...))


BUILDERS = [_dataclass, _typeddict, _pydantic]
PAIRS = [(list[int], list[Annotated[int, Ge(5)]]),
         (Optional[list[int]], Optional[list[Annotated[int, Ge(5)]]])]


@pytest.mark.parametrize("build", BUILDERS)
@pytest.mark.parametrize("older,newer", PAIRS)
def test_an_item_bound_is_not_proven_away(build, older, newer):
    assert smt._schema_inclusion(build(older), build(newer)).verdict != "proven"


@pytest.mark.parametrize("build", BUILDERS)
def test_the_same_list_type_stays_proven(build):
    assert smt._schema_inclusion(build(list[int]), build(list[int])).verdict == "proven"
