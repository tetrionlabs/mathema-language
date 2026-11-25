# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A pattern that one supported Python compiles and another refuses is
refused for that other Python, and for every supported Python at once.

`\\N{SHAKING FACE}` names U+1FAE8, added in Unicode 15.0: Python 3.12 and
later compile it, 3.10 and 3.11 refuse it (`re.error: undefined character
name`). `(?(١)b|c)` refers to a group by a non-ASCII digit: 3.10 and 3.11
compile it, 3.12 and later refuse it. Neither is visible in the parse
tree, so the regex delta table's construct names (`literal`,
`conditional`, both read alike) do not show the difference."""
import pytest

from mathema_language import words
from mathema_language.text import _regular

SHAKING_FACE = r"\N{SHAKING FACE}"
DIGIT_REFERENCE = "(a)?(?(١)b|c)"


@pytest.mark.parametrize("version", ["3.10", "3.11", None])
def test_a_character_name_newer_than_the_pinned_python_is_refused(version):
    with pytest.raises((_regular.NotRegular, ValueError)):
        _regular.term(SHAKING_FACE, 0, "matches", version=version)


@pytest.mark.parametrize("version", ["3.12", "3.13", "3.14", None])
def test_a_group_reference_by_a_non_ascii_digit_is_refused_for_a_python_that_refuses_it(version):
    with pytest.raises((_regular.NotRegular, ValueError)):
        _regular.term(DIGIT_REFERENCE, 0, "matches", version=version)


@pytest.mark.parametrize("argument", [f're(r"{SHAKING_FACE}", python 3.10)', f're(r"{SHAKING_FACE}", python)'])
def test_the_word_refuses_the_character_name_for_a_python_that_does_not_know_it(argument):
    with pytest.raises(ValueError):
        words._canonical_pattern_argument(argument)
