# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A pattern word reads a call in code as its predicate only where the
call's truth on a text is exactly that predicate: a compiled pattern's
bound method, or `functools.partial` of the `re` function with the
pattern alone (and flags by keyword). A partial that binds the text
itself, binds anything else, or gives flags beside a compiled pattern
(which `re` refuses) is not read, and nothing raises."""
import functools
import re

import pytest

from mathema_language import words


@pytest.mark.parametrize("word, callee, want", [
    ("matches", re.compile(r"[a-z]+").fullmatch, 're(r"[a-z]+", python)'),
    ("contains", re.compile(r"ab").search, 're(r"ab", python)'),
    ("matches", functools.partial(re.fullmatch, r"[a-z]+"), 're(r"[a-z]+", python)'),
    ("starts with", functools.partial(re.match, r"ab", flags=re.I), 're(r"ab", python, ignore case)'),
    ("matches", functools.partial(re.fullmatch, re.compile(r"a", re.I)), 're(r"a", python, ignore case)'),
])
def test_a_call_that_is_the_predicate_is_read(word, callee, want):
    assert words._reads_call(word, callee) == (want,)


@pytest.mark.parametrize("callee", [
    functools.partial(re.fullmatch, r"a+", "aaa"),
    functools.partial(re.fullmatch, r"a+", "aaa", re.I),
    functools.partial(re.fullmatch, re.compile(r"a"), flags=re.I),
    functools.partial(re.fullmatch, r"a+", string="aaa"),
    functools.partial(re.fullmatch, r"a+", flags="i"),
    functools.partial(re.fullmatch, pattern=r"a+"),
    functools.partial(re.search, r"a+"),
    re.compile(r"a").search,
])
def test_a_call_that_is_not_the_predicate_is_not_read(callee):
    assert words._reads_call("matches", callee) is None
