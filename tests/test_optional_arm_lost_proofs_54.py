# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""True inclusions the encoding proved before the per-field strict decline and the both-levels
keyword decline, and no longer does."""
from typing import Annotated

import pytest

pytest.importorskip("z3")
pytest.importorskip("pydantic")
pytest.importorskip("jsonschema")

from pydantic import ConfigDict, Field, StrictInt, create_model  # noqa: E402

from mathema_language import smt  # noqa: E402


def test_strict_int_in_a_strict_model_is_still_proven():
    cfg = ConfigDict(strict=True)
    a = create_model("A", __config__=cfg, x=(StrictInt, ...))
    b = create_model("B", __config__=cfg, x=(StrictInt, ...))
    assert smt._schema_inclusion(a, b).verdict == "proven"


def test_field_strict_false_on_the_older_side_is_still_proven():
    a = create_model("A", x=(Annotated[int, Field(strict=False)], ...))
    b = create_model("B", x=(int, ...))
    assert smt._schema_inclusion(a, b).verdict == "proven"


@pytest.mark.xfail(strict=True, reason="owed: multipleOf on both levels combines to their least "
                   "common multiple; declined in 0.4.2, restored by 2026-12-18")
def test_multiple_of_on_both_levels_combines():
    obj = lambda p: {"type": "object", "required": ["x"], "properties": {"x": p}}  # noqa: E731
    older = obj({"anyOf": [{"type": "integer", "multipleOf": 6}, {"type": "null"}]})
    newer = obj({"multipleOf": 2, "anyOf": [{"type": "integer", "multipleOf": 3}, {"type": "null"}]})
    assert smt._schema_inclusion(older, newer).verdict == "proven"
