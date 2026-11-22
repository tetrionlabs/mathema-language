# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A lone surrogate is a value an alphabet can hold, and the alphabet's
canonical text names it with its escape, so the text reads back to the
same alphabet, alone, beside other characters and as a pattern's binding.
Two surrogates written together are two characters, not one."""
import pytest

from mathema_language import words
from mathema_language.text.alphabets import parse_alphabet


@pytest.mark.parametrize("expression, codes", [
    ('"\\ud800"', [0xD800]),
    ('"\\udfff"', [0xDFFF]),
    ('lower + "\\ud83d"', [0xD83D]),
    ('"\\ud83d\\ude00"', [0xD83D, 0xDE00]),
    ('"\\ud800" + "é" + "\\n"', [0xD800]),
])
def test_an_alphabet_with_a_lone_surrogate_reads_back(expression, codes):
    found = parse_alphabet(expression)
    assert all(any(lo <= c <= hi for lo, hi in found.ranges) for c in codes)
    again = parse_alphabet(found.text)
    assert again.ranges == found.ranges
    assert again.text == found.text
    assert found.text.isascii() or all(not 0xD800 <= ord(c) <= 0xDFFF for c in found.text)


def test_a_lone_surrogate_binding_reads_back_through_the_pattern_word():
    found = parse_alphabet('"\\ud800"')
    shape = words._read_pattern(['"W"', "W = " + found.text])
    assert shape.bindings[0][1].ranges == found.ranges
    again = words._read_pattern(words._split(words._pattern_text(shape, call=False)))
    assert again == shape
