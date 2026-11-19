# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The hazards a text or path language draws test how code reads awkward
text, never what it does to a real place: no path that names a system
file, a home directory, a repository's own files, the filesystem root or
the current directory, none that climbs out of where it starts, no
network host and no code."""
import random
import re

import pytest

_DANGEROUS = re.compile(
    r"(?i)^(\.|/|\.\.|--?[a-z]+)$|(^|/)\.\.(/|$)|/etc/|~|\.git(/|$)|\.ssh|"
    r"^\\\\|://|^www\.|javascript:|drop\s+table|;\s*--")


def _dangerous(values):
    return [v for v in values if _DANGEROUS.search(v)]


def test_the_text_hazards_name_no_real_place():
    from mathema_language.text.hazards import TEXT_HAZARDS
    assert _dangerous(h.value for h in TEXT_HAZARDS) == []


@pytest.mark.parametrize("which", ["path", "within"])
def test_the_path_hazards_name_no_real_place(which):
    from mathema_language.text.path_language import PATH, path_within
    lang = PATH if which == "path" else path_within("/srv/app")
    assert _dangerous(h.value for h in lang.hazards()) == []


@pytest.mark.parametrize("which", ["path", "within"])
def test_a_path_outside_the_language_names_no_real_place(which):
    from mathema_language.text.path_language import PATH, path_within
    lang = PATH if which == "path" else path_within("/srv/app")
    rng = random.Random(0)
    drawn = [lang.outside(rng) for _ in range(200)]
    assert _dangerous(v for v in drawn if v is not None) == []
