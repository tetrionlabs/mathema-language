# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""`mathema_language.text.pattern_language`, the 0.4.0 name of
`regex_language`, still reads a pattern the same way for 0.4.x, and
warns that the name is deprecated and names the one to use."""
import pytest

from mathema_language import text
from mathema_language.text import regex_language


def test_the_old_name_gives_the_same_language_and_warns():
    with pytest.warns(DeprecationWarning, match="regex_language"):
        old = text.pattern_language(r"[a-z]+", "contains")
    new = regex_language(r"[a-z]+", "contains")
    assert old.name == new.name and old.to_json() == new.to_json()
    for sample in ["", "a", "ab1", "1", "A"]:
        assert old.contains(sample) == new.contains(sample)
