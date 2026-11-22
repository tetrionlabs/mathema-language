# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The canonical text of a `re(...)` argument reads back to itself:
every inline flag group at the start of the pattern is taken out and
read as flags, however many there are."""
import pytest

from mathema_language import words


@pytest.mark.parametrize("text, same_as", [
    ('re(r"(?i)(?m)a")', 're(r"(?im)a")'),
    ('re(r"(?m)(?i)a")', 're(r"(?im)a")'),
    ('re(r"(?i)(?s)(?m)a")', 're(r"(?ims)a")'),
    ('re(r"(?i)(?i)a")', 're(r"(?i)a")'),
])
def test_leading_flag_groups_are_all_read_as_flags(text, same_as):
    canonical = words.canonical_pattern_argument(text)
    assert canonical == words.canonical_pattern_argument(same_as)
    assert words.canonical_pattern_argument(canonical) == canonical
    assert "(?" not in canonical


def test_a_scoped_flag_group_at_the_start_stays_in_the_pattern():
    canonical = words.canonical_pattern_argument('re(r"(?i:a)b")')
    assert canonical.startswith('re(r"(?i:a)')
    assert words.canonical_pattern_argument(canonical) == canonical
