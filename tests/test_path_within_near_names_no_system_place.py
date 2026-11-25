# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""No value `path_within` offers outside a root names a system
directory, for a root that starts with two slashes. POSIX keeps a
leading `//` through `normpath`, and on Linux and macOS `//etc` is
`/etc`, so the root's name cut short, `//etc` beside `//etcd`, names the
system directory."""
import posixpath
import random

import pytest

from mathema_language.text.path_language import SYSTEM_DIRECTORIES, path_within


def _system(path: str) -> bool:
    if not path.startswith("/"):
        return False
    segments = ("/" + posixpath.normpath(path).lstrip("/")).split("/")[1:]
    return bool(segments) and segments[0] in SYSTEM_DIRECTORIES


@pytest.mark.parametrize("root", ["//etcd", "//tmpx", "//usr2", "//varx"])
def test_no_value_outside_a_double_slash_root_is_a_system_directory(root):
    language = path_within(root)
    rng = random.Random(0)
    offered = {language.outside(rng) for _ in range(200)} | {h.value for h in language.near}
    assert not [p for p in offered if isinstance(p, str) and _system(p)]
