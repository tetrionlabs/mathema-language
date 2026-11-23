# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""`contains` with a pattern anchored at one end still draws text on its
open side. `beside` adds text before and after together, so for
`contains (re(r"\\Aab"))` every addition is refused and every draw is
"ab", though "abx" is a member."""
import random

import pytest

from mathema_language.text import _regular


@pytest.mark.parametrize("pattern", [r"\Aab", r"ab\Z"])
def test_an_anchored_contains_draws_a_member_longer_than_the_match(pattern):
    language = _regular.regex_language(pattern, "contains", 0)
    rng = random.Random(0)
    draws = [language.sample(rng) for _ in range(300)]
    assert all(language.contains(d) for d in draws)
    assert any(d != "ab" for d in draws)
