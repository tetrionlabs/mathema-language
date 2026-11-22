# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A pattern is parsed by the running interpreter's `re`, so a language
about another Python is built only from constructs every supported
version reads alike, or those the shipped version table records for the
versions it covers. A construct the regex delta table does not show
reading alike on the other version (global flags after the start, read
by 3.10 and refused from 3.11) is refused for any other version and for every version at once,
and a possessive repeat or atomic group is refused for 3.10, by
`regex_language` and the `re(...)` word alike, whichever supported
Python runs them."""
import warnings

import pytest

from mathema_language import words
from mathema_language.text import _regular, regex_language

OTHERS = [v for v in _regular.versions_data()["versions"] if v != _regular.RUNNING]


@pytest.mark.parametrize("version", [*OTHERS, None])
def test_global_flags_after_the_start_are_refused_for_another_python(version):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with pytest.raises(ValueError):
            regex_language("a(?i)b", version=version)


@pytest.mark.parametrize("version", OTHERS)
def test_the_word_refuses_global_flags_after_the_start_for_another_python(version):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with pytest.raises(ValueError):
            words._canonical_pattern_argument(f're(r"a(?i)b", python {version})')


@pytest.mark.parametrize("pattern", ["a*+", "(?>a)b", "a{1,2}+"])
def test_the_word_refuses_a_possessive_or_atomic_pattern_pinned_to_3_10(pattern):
    if _regular.RUNNING == "3.10":
        pytest.skip("3.10 does not compile the pattern, so nothing is read")
    with pytest.raises(ValueError, match="3.10"):
        words._canonical_pattern_argument(f're(r"{pattern}", python 3.10)')
    with pytest.raises(ValueError, match="3.10"):
        regex_language(pattern, version="3.10")


@pytest.mark.parametrize("version", OTHERS)
@pytest.mark.parametrize("pattern", [r"[a-z]+", r"\d{2}-\w+", r"(?i)colou?r", r"^a|b$", r"(a|bc)*"])
def test_a_pattern_every_version_reads_alike_is_read_for_another_python(pattern, version):
    language = regex_language(pattern, version=version)
    assert language.to_json()["term"]["source"]["versions"] == [version]
    canonical = words._canonical_pattern_argument(f're(r"{pattern}", python {version})')
    assert f"python {version}" in canonical
