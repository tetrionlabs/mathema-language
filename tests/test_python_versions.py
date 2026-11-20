# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""What the supported Pythons read differently, and the terms that cover them.

The shipped data file states, for each supported Python, its Unicode
version and the characters of every class that depends on it
(`tests/_python_version_data.py` generates it). A term without a version
is the same on every supported interpreter and brackets all of them; a
term with one is that version's. The hashes of a fixed list of terms are
committed, compared here on the running interpreter, and, with
`MATHEMA_PYTHONS` set to a list of versions, on each of those through
`uv`."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from mathema_language.text import _regular as rx
from tests import _python_term_hashes as recorded
from tests import _python_version_data as generator

DATA = rx.versions_data()
HERE = rx.RUNNING


def _points(spans):
    return {c for lo, hi in spans for c in range(lo, hi + 1)}


def test_the_supported_versions_are_stated_with_their_unicode():
    assert DATA["dialect"] == "python"
    assert DATA["versions"] == ["3.10", "3.11", "3.12", "3.13", "3.14"]
    assert len(set(DATA["unicode"].values())) >= 4


@pytest.mark.skipif(HERE not in DATA["versions"], reason="this Python is not in the data file")
def test_this_python_reads_what_the_file_says_for_its_version():
    import unicodedata
    assert DATA["unicode"][HERE] == unicodedata.unidata_version
    for name, inside in generator.CLASSES.items():
        here = {c for c in range(0x110000) if inside(chr(c))}
        assert _points(DATA["classes"][name]["by_version"][HERE]) == here, name
    engine = DATA["engine"]
    assert (HERE in engine["not_boundary_in_empty"]) == (re.search(r"\B", "") is not None)
    assert (HERE in engine["possessive_and_atomic"]) == (sys.version_info >= (3, 11))


def test_a_class_is_the_common_characters_and_each_version_own():
    for name, entry in DATA["classes"].items():
        common = _points(entry["common"])
        assert common == set.intersection(*[_points(s) for s in entry["by_version"].values()])
        low, high = rx.class_bounds(name)
        assert _points(low) == common and _points(entry["any"]) <= _points(high)
        assert _points(DATA["unassigned"]) <= _points(high)


ITEMS = [r"\d", r"\w", r"\s", r"\D", r"\W", r"\S", r"[\d\s]", r"[^\w]", r"[^\W\d]", r"[\w-]", r"a",
         r"[^a]", r"[a-zà-ÿ]", r"[^\n\d]", r"."]


@pytest.mark.skipif(HERE not in DATA["versions"], reason="this Python is not in the data file")
@pytest.mark.parametrize("pattern", ITEMS)
@pytest.mark.parametrize("flags", [0, re.A, re.S])
def test_a_class_read_from_the_file_is_what_re_matches_here(pattern, flags):
    doc = rx.term(pattern, flags, "matches", version=HERE)
    assert doc["exact"]
    node = doc["language"]
    spans = node["ranges"] if node["op"] == "chars" else [[c, c] for c in node["codes"]]
    assert tuple((lo, hi) for lo, hi in spans) == rx._class_chars(pattern, flags)


@pytest.mark.parametrize("pattern, flags, exact", [
    (r"^[a-z0-9]+(?:-[a-z0-9]+)*$", 0, True), (r"\w+", re.A, True), (r"(?i)[a-z]+k", 0, True),
    (r"a$", re.M, True), (r".", 0, True), (r"\w+", 0, False), (r"\d", 0, False), (r"\s", 0, False),
    (r"\bx", 0, False), (r"\bx", re.A, True), (r"\B", re.A, False), (r"(?i)\w", 0, False),
    (r"[^\W\d]", 0, False), (r"(?i)\U00010570", 0, False),
])
def test_without_a_version_a_term_is_exact_only_where_every_python_agrees(pattern, flags, exact):
    doc = rx.term(pattern, flags, "contains")
    assert doc["exact"] == exact
    assert doc["source"]["versions"] == DATA["versions"]
    assert doc["source"]["unicode"] == list(dict.fromkeys(DATA["unicode"].values()))
    if not exact:
        assert doc["source"]["not_exact"]


def test_the_bounds_hold_the_characters_every_version_and_any_version_reads():
    doc = rx.term(r"\w", 0, "matches")
    newest_only = next(c for c in sorted(_points(DATA["classes"]["word"]["by_version"]["3.14"])
                                         - _points(DATA["classes"]["word"]["common"])))
    unassigned = DATA["unassigned"][0][0]
    assert rx.member(doc, "a", "at_most") and rx.member(doc, "é", "at_most")
    assert rx.member(doc, chr(newest_only), "at_least") and not rx.member(doc, chr(newest_only), "at_most")
    assert rx.member(doc, chr(unassigned), "at_least") and not rx.member(doc, chr(unassigned), "at_most")
    assert not rx.member(doc, " ", "at_least")
    outside = rx.term(r"\W", 0, "matches")
    assert rx.member(outside, chr(newest_only), "at_least")
    assert not rx.member(outside, chr(newest_only), "at_most")
    assert rx.member(outside, " ", "at_most")


def test_a_version_gives_that_python_reading_on_any_interpreter():
    old, new = rx.term(r"\w", 0, "matches", version="3.10"), rx.term(r"\w", 0, "matches", version="3.14")
    newest_only = next(c for c in sorted(_points(DATA["classes"]["word"]["by_version"]["3.14"])
                                         - _points(DATA["classes"]["word"]["by_version"]["3.10"])))
    assert old["exact"] and new["exact"] and old["source"]["versions"] == ["3.10"]
    assert rx.member(new, chr(newest_only)) and not rx.member(old, chr(newest_only))
    assert rx.term_hash(old) != rx.term_hash(new)
    with pytest.raises(ValueError, match="supported"):
        rx.term("a", 0, "matches", version="3.9")


def test_not_boundary_in_the_empty_string_follows_the_version():
    assert not rx.member(rx.term(r"\B", re.A, "matches", version="3.13"), "")
    assert rx.member(rx.term(r"\B", re.A, "matches", version="3.14"), "")
    both = rx.term(r"\B", re.A, "matches")
    assert rx.member(both, "", "at_least") and not rx.member(both, "", "at_most")
    assert "\\B in the empty string" in both["source"]["not_exact"]


@pytest.mark.skipif(sys.version_info < (3, 11), reason="possessive repeats need 3.11")
def test_a_construct_some_versions_do_not_read_needs_a_version():
    for pattern in (r"a*+a", r"(?>a)b"):
        with pytest.raises(rx.NotRegular, match=r"python 3\.10 does not read"):
            rx.term(pattern)
        with pytest.raises(rx.NotRegular, match=r"python 3\.10 does not read"):
            rx.term(pattern, version="3.10")
        assert not rx.term(pattern, version="3.12")["exact"]


def test_the_characters_a_verdict_could_turn_on_are_named():
    newest_only = next(c for c in sorted(_points(DATA["classes"]["decimal"]["by_version"]["3.14"])
                                         - _points(DATA["classes"]["decimal"]["common"])))
    unassigned = DATA["unassigned"][0][0]
    found = rx.version_dependent_characters("a1٣" + chr(newest_only) + chr(unassigned))
    assert [f["code"] for f in found] == [newest_only, unassigned]
    digit = found[0]["classes"]["decimal"]
    assert "3.14" in digit["in"] and "3.10" in digit["not_in"]
    assert found[1]["unassigned"] and not found[0]["unassigned"]
    assert rx.version_dependent_characters("plain ascii é") == []


# -- the same term on every interpreter -----------------------------------------

def test_the_terms_built_here_have_the_committed_hashes():
    committed = json.loads(recorded.HASHES.read_text())
    assert len(committed) >= 200
    assert recorded.hashes() == committed


@pytest.mark.skipif(not os.environ.get("MATHEMA_PYTHONS"), reason="set MATHEMA_PYTHONS, e.g. 3.10,3.14")
def test_every_listed_interpreter_builds_the_committed_hashes():
    committed = json.loads(recorded.HASHES.read_text())
    script = str(Path(recorded.__file__))
    for version in os.environ["MATHEMA_PYTHONS"].split(","):
        done = subprocess.run(["uv", "run", "--python", version.strip(), "--no-project", "python", script],
                              capture_output=True, text=True, check=True)
        assert json.loads(done.stdout) == committed, version
