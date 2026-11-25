# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The draws of `contains`, `starts with` and `ends with` hold text
beside the match, not only texts the pattern matches in full. Every
draw of `L[ascii, ends with ("ab")]` is "ab", so a probe of
`for s in L[ascii, $= "ab"], s.startswith("ab") == True` reports holds,
though "xab" is a member and breaks it."""
import random

import pytest

from mathema_language.text import _regular


@pytest.mark.parametrize("word", ["contains", "starts with", "ends with"])
@pytest.mark.parametrize("pattern", ["ab", "a[0-9]+"])
def test_draws_include_a_member_the_pattern_does_not_match_in_full(word, pattern):
    language = _regular.regex_language(pattern, word, 0)
    rng = random.Random(0)
    draws = [language.sample(rng) for _ in range(300)]
    assert all(language.contains(d) for d in draws)
    assert any(not _regular.runs(pattern, 0, "matches", d) for d in draws)
