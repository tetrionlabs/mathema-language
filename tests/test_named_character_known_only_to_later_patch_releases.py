# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A named character that some patch releases of one Python know and
others do not is refused for that Python. `\\N{TANGUT IDEOGRAPH-17000}`
compiles on 3.13.16 and 3.14.8 and is refused by 3.13.1 and 3.14.0b4,
though each pair reports one Unicode version (15.1.0, 16.0.0): the
algorithmic Tangut names were added to the name lookup in a patch
release. The delta table keys a reading by major and minor version, so
a term pinned to 3.13 or 3.14 is not the reading of every 3.13 or 3.14."""
import pytest

from mathema_language.text import _regular

TANGUT = r"\N{TANGUT IDEOGRAPH-17000}"


@pytest.mark.parametrize("version", ["3.13", "3.14"])
def test_a_named_character_some_patch_releases_refuse_is_refused_for_that_python(version):
    with pytest.raises((_regular.NotRegular, ValueError)):
        _regular.term(TANGUT, 0, "matches", version=version)
