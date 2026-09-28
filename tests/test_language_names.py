# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The language names read as English and follow one rule: `digit`,
`alpha` and `alnum` are ASCII, `unicode_alpha` and `unicode_alnum` are
any script, and the alphabets of characters code gets wrong are named
for what they hold."""
import pytest

pytest.importorskip("mathema")

from mathema.languages import UnknownLanguage, resolve_language  # noqa: E402


@pytest.mark.parametrize("name,member,other", [
    ("alpha", "Abc", "é"),
    ("alnum", "Ab1", "٣"),
    ("unicode_alpha", "éα", "1"),
    ("unicode_alnum", "é٣", "-"),
    ("control", "\n\x00", "a"),
    ("invisible", "​﻿", "a"),
    ("compatibility", "ﬁ℀", "a"),
    ("astral", "\U0001f600", "a"),
])
def test_each_name_holds_what_it_says(name, member, other):
    language = resolve_language(name)
    assert language.contains(member) and not language.contains(other)


@pytest.mark.parametrize("old", ["c0", "format", "nfkc_folding", "non_bmp"])
def test_the_old_names_are_gone(old):
    with pytest.raises(UnknownLanguage):
        resolve_language(old)
