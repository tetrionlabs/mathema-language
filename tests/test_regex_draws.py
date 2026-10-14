# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Text drawn from a pattern matches it, the negated categories (`\\S`,
`\\D`, `\\W`) included, and a record whose text field has such a
pattern has members to draw."""
import random
import re

import pytest

from mathema_language.text.regex import draw_matching


@pytest.mark.parametrize("pattern", [r"^\S+@\S+\.\w{2,}$", r"\D{3}", r"\W\w", r"[^\s]+",
                                     r"^\w{2,4}-\d+$", r"colou?r"])
def test_a_drawn_string_matches_its_pattern(pattern):
    rng = random.Random(0)
    for _ in range(20):
        s = draw_matching(rng, pattern)
        assert s is not None and re.fullmatch(pattern, s), (pattern, s)


def test_a_record_with_an_email_like_pattern_has_members():
    pydantic = pytest.importorskip("pydantic")
    from mathema_language.schema.adaptors import adapt_row

    class Contact(pydantic.BaseModel):
        email: str = pydantic.Field(pattern=r"^\S+@\S+\.\w{2,}$")

    language = adapt_row(Contact)
    rng = random.Random(0)
    assert all(language.contains(language.sample(rng)) for _ in range(20))
