# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A term for every supported Python brackets a class that differs
between them: `at_most` holds only what every version admits, and
`at_least` everything any version admits. U+A7CB (LATIN CAPITAL LETTER
RAMS HORN, Unicode 16.0) is matched by `\\w` on Python 3.14 and by no
earlier supported Python."""
from mathema_language.text import _algebra, _regular

RAMS_HORN = "Ɤ"


def test_a_character_only_a_later_python_admits_is_in_at_least_and_not_in_at_most():
    doc = _regular.term(r"\w", 0, "matches")
    assert not doc["exact"]
    assert _algebra.member(doc, RAMS_HORN, "at_least")
    assert not _algebra.member(doc, RAMS_HORN, "at_most")
