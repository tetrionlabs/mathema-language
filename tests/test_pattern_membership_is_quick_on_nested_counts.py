# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Membership of a pattern whose longest member is within `MAX_LENGTH`
is decided in bounded time on a text of a few hundred characters. The
term's matcher takes about 30 seconds on a 201-character text for
`[[a]{0,50}]{0,50}`, and over a minute on 500 characters for
`[X{0,30}X{0,30}]{0,100}`; the direct reading takes milliseconds."""
import time

import pytest

from mathema_language.text.pattern import Pattern


@pytest.mark.parametrize("picture, text", [("[[a]{0,50}]{0,50}", "a" * 201),
                                           ("[X{0,30}X{0,30}]{0,100}", "x" * 500)])
def test_membership_takes_under_two_seconds(picture, text):
    language = Pattern(picture, "unicode").language()
    started = time.monotonic()
    language.contains(text)
    assert time.monotonic() - started < 2
