# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A version after the dialect in `re(...)`: `python 3.13` is that
Python's reading, `python` alone every supported Python's."""
import re

import pytest

from mathema_language import words
from mathema_language.text import _regular as rx

OTHER = next(v for v in rx.versions_data()["versions"] if v != rx.RUNNING)


@pytest.mark.parametrize("written, version, canonical", [
    ('re(r"\\w+", python 3.13)', "3.13", 're(r"\\w+", python 3.13)'),
    ('re(r"\\w+", py 3.10, ignore case)', "3.10", 're(r"\\w+", python 3.10, ignore case)'),
    ('re(r"\\w+", ignore case, Python  3.12)', "3.12", 're(r"\\w+", python 3.12, ignore case)'),
    ('re(r"\\w+", python)', None, 're(r"\\w+", python)'),
    ('re(r"\\w+")', None, 're(r"\\w+", python)'),
])
def test_a_version_after_the_dialect_is_read_and_written_back(written, version, canonical):
    assert words._re_version(written) == version
    assert words.canonical_pattern_argument(written) == canonical
    assert words.canonical_pattern_argument(canonical) == canonical
    pattern, flags = words.read_re(written)
    assert words.re_text(pattern, flags, version) == canonical


@pytest.mark.parametrize("written, said", [
    ('re(r"a", python 3.9)', "python 3.9 is not a supported version; the versions are 3.10, 3.11, 3.12, 3.13, 3.14"),
    ('re(r"a", python 3.13.2)', "a version is written python 3.13"),
    ('re(r"a", 3.13)', "a version is written python 3.13"),
    ('re(r"a", python 3.13, python 3.12)', "re names one dialect"),
])
def test_a_version_that_does_not_read_says_why(written, said):
    with pytest.raises(ValueError) as caught:
        words.read_re(written)
    assert said in str(caught.value)


def test_the_language_of_a_pinned_pattern_is_that_python_reading():
    pinned = words._pattern_language_of('re(r"\\w+", python 3.10)', "matches", "unicode")
    doc = pinned.to_json()["definition"]
    assert doc["exact"] and doc["source"]["versions"] == ["3.10"]
    assert doc == rx.term(r"\w+", 0, "matches", version="3.10")
    every = words._pattern_language_of('re(r"\\w+", python)', "matches", "unicode")
    assert not every.to_json()["definition"]["exact"]
    assert every.contains("éa")


def test_a_language_about_another_python_refuses_to_run_here():
    pinned = words._pattern_language_of(f're(r"\\w+", python {OTHER})', "contains", "unicode")
    with pytest.raises(rx.OtherVersion, match=f"this claim is about python {OTHER}"):
        pinned.contains("a")
    here = words._pattern_language_of(f're(r"\\w+", python {rx.RUNNING})', "contains", "unicode")
    assert here.contains("xa") and here.to_json()["definition"]["exact"]


def test_a_literal_and_an_ascii_pattern_need_no_version():
    assert words._pattern_language_of('"a.b"', "contains", "unicode").contains("xa.b")
    doc = words._pattern_language_of('re(r"[a-z]+", python)', "matches", "unicode").to_json()["definition"]
    assert doc["exact"] and re.fullmatch("[a-z]+", "abc")
