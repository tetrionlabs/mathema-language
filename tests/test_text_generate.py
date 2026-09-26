# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Drawing by Unicode category across the planes reaches every plane
and category asked for, and never a surrogate or an unassigned code
point unless asked."""
import random
import unicodedata

from mathema_language.text import generate


def test_each_requested_plane_is_reached():
    rng = random.Random(1)
    planes = (0, 1, 2, 14, 15, 16)
    seen = set()
    for _ in range(600):
        ch = generate.draw_char(rng, (), planes)
        seen.add(ord(ch) >> 16)
    assert seen >= set(planes)


def test_categories_are_honoured():
    rng = random.Random(2)
    for _ in range(300):
        ch = generate.draw_char(rng, ("Lu", "Ll"), (0, 1))
        assert unicodedata.category(ch) in ("Lu", "Ll")


def test_surrogates_and_unassigned_only_on_request():
    rng = random.Random(3)
    for _ in range(500):
        ch = generate.draw_char(rng, (), (0, 15, 16))
        assert unicodedata.category(ch) not in ("Cs", "Cn")
    assert unicodedata.category(generate.draw_char(rng, ("Cs",), (0,))) == "Cs"


def test_lengths_are_short_most_of_the_time_and_long_sometimes():
    rng = random.Random(4)
    lengths = [generate.draw_length(rng) for _ in range(500)]
    assert max(lengths) >= 64 and sum(1 for n in lengths if n <= 12) > 400
