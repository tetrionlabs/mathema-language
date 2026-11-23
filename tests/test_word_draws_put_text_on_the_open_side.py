# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The draws of a pattern word reach the members a probe needs to see,
with no core: `ends with` draws texts that end with the match and do not
start with it, `starts with` the reverse, and `contains` texts with
text on each side alone and on both, for a regular expression and for a
picture pattern alike. Every draw is a member. Seeded."""
import random

import pytest

from mathema_language import words

CASES = [('re(r"ab", python)', "ab", "ascii"), ('pattern("\'ab\'")', "ab", "ascii")]


def _draws(argument, word, base, n=400):
    language = words._regex_language_of(argument, word, base)
    rng = random.Random(11)
    drawn = [language.sample(rng) for _ in range(n)]
    assert all(language.contains(d) for d in drawn), (argument, word)
    return drawn


@pytest.mark.parametrize("argument, match, base", CASES)
def test_ends_with_draws_text_before_the_match_only(argument, match, base):
    drawn = _draws(argument, "ends with", base)
    assert any(d.endswith(match) and not d.startswith(match) for d in drawn)
    assert all(d.endswith(match) for d in drawn)


@pytest.mark.parametrize("argument, match, base", CASES)
def test_starts_with_draws_text_after_the_match_only(argument, match, base):
    drawn = _draws(argument, "starts with", base)
    assert any(d.startswith(match) and not d.endswith(match) for d in drawn)
    assert all(d.startswith(match) for d in drawn)


@pytest.mark.parametrize("argument, match, base", CASES)
def test_contains_draws_text_on_each_side_alone_and_on_both(argument, match, base):
    drawn = [d for d in _draws(argument, "contains", base) if d.count(match) == 1]
    assert any(d.startswith(match) and len(d) > len(match) for d in drawn)
    assert any(d.endswith(match) and len(d) > len(match) for d in drawn)
    assert any(not d.startswith(match) and not d.endswith(match) for d in drawn)
