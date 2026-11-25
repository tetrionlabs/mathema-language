# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The canonical text of a pattern word reads back to the same pattern,
for a picture holding a character a string literal cannot hold bare: a
line feed, a carriage return, a NUL or a lone surrogate. The picture is
quoted by `pattern._quoted`, which escapes only the backslash and the
double quote, so the canonical text has the character bare between the
quotes and does not read as a string literal."""
import pytest

from mathema_language import words


@pytest.mark.parametrize("picture", ["a\n9", "a\r9", "\x00", "a\ud800"])
def test_the_canonical_text_of_a_picture_reads_back_to_itself(picture):
    canonical = words._canonical_pattern_argument("pattern(" + words._quoted(picture) + ")")
    assert words._canonical_pattern_argument(canonical) == canonical
    assert words._text_pattern_of(canonical, "unicode").text == picture
