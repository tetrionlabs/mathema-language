# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The region text of `within` has one reading: `within_arguments` reads
each quoted region as a string literal, as the word does, and a path
language's own name reads back to its roots. No value a path language
offers outside itself climbs through `.` or `..`, or names a place at
or under a system directory, whatever the root."""
import random

import pytest

from mathema_language import words
from mathema_language.text.path_language import path_within
from mathema_language.text.within import within_arguments


@pytest.mark.parametrize("written", ['"/a\\tb"', '"/a\\nb"', '"/q\\"d"', '"/b\\\\c"', '"/é"',
                                     '"/a\\x00b"', '"/a\\u2028b"', '"/a b"'])
def test_within_arguments_reads_a_region_as_the_word_does(written):
    assert within_arguments(f"within ({written})") == (words._string(written),)
    assert within_arguments(f"within {written}") == (words._string(written),)


@pytest.mark.parametrize("roots", [("/a\tb",), ("/a\nb",), ('/q"d', "/b\\c"), ("/é", "/a b"),
                                   ("/a\u2028b",)])
def test_a_path_language_s_name_reads_back_to_its_roots(roots):
    language = path_within(*roots)
    written = language.name.split(", ", 1)[1]
    assert within_arguments(written) == roots


_SYSTEM = {"bin", "boot", "dev", "etc", "home", "lib", "lib64", "opt", "proc", "root", "run",
           "sbin", "srv", "sys", "tmp", "usr", "var", "Applications", "Library", "System",
           "Users", "Volumes", "private"}


@pytest.mark.parametrize("root", ["/etcd", "/a/..b", "/a/.b", "/tmpx", "/dev1", "/usr2", "/varx",
                                  "/workspace", "/srv/app", "/usr/localx", "/a/..", "/home2"])
def test_no_value_outside_a_path_language_climbs_or_names_a_system_place(root):
    try:
        language = path_within(root)
    except ValueError:
        return
    rng = random.Random(1)
    for _ in range(400):
        value = language.outside(rng)
        if value is None:
            continue
        segments = value.split("/")
        assert "." not in segments[1:] and ".." not in segments, (root, value)
        if value.startswith("/"):
            assert segments[1] not in _SYSTEM, (root, value)
