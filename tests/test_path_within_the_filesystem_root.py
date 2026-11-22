# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The filesystem root `/` holds every absolute path with no `..`
segment, a doubled slash included, as every other root holds the paths
under it."""
import pytest

from mathema_language.text.path_language import path_within


@pytest.mark.parametrize("text, inside", [
    ("/", True), ("//a", True), ("//", True), ("/a//b", True), ("///a/", True),
    ("/..", False), ("//..", False), ("/a/../b", False), ("a", True), ("..", False)])
def test_the_filesystem_root_holds_every_absolute_path_without_a_climb(text, inside):
    assert path_within("/").contains(text) is inside
