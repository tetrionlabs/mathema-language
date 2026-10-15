# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""`L[path]` is any non-empty path text without a NUL, and
`path_within(root)` the paths confined to a root: no `..` segment, and an
absolute path only at or under the root. Both resolve and pass mathema's
language checks, draw members that are members, offer hazards that are
members and outside values that are not, and the z3 encoding of their
pattern agrees with the pattern on every case, on both sides. Over a
command line, a path option whose choices all stay inside is proven
within the root, and one that can name anything is falsified with the
value a program would receive."""
import argparse
import random
from pathlib import Path

import mathema.languages as languages
import pytest

from mathema_language.text.path_language import PATH, path_within

WS = path_within("/ws")

CASES = {
    "a": True, "a/b": True, "a//b": True, "./a": True, ".": True, "...": True, "-rf": True,
    ".git/config": True, "/ws": True, "/ws/": True, "/ws/a": True,
    "a/..": False, "a/../b": False, "../x": False, "..": False, "/ws/../x": False,
    "/wsx": False, "/etc": False, "/": False, "": False, "a\x00b": False,
}


def test_both_are_languages_and_path_resolves_by_name():
    assert languages.language_problems(PATH) == []
    assert languages.language_problems(WS) == []
    assert languages.resolve_language("path") is PATH
    assert WS.render(True) == 'L[path, within "/ws"]'


@pytest.mark.parametrize("text, inside", CASES.items(), ids=repr)
def test_within_admits_exactly_the_paths_that_name_no_climb_out(text, inside):
    assert WS.contains(text) == inside
    assert PATH.contains(text) == (text != "" and "\x00" not in text)


def test_the_filesystem_root_admits_every_absolute_path_without_a_climb():
    top = path_within("/")
    assert top.contains("/etc") and top.contains("/") and not top.contains("/a/../../b")


@pytest.mark.parametrize("root", ["relative", "/a/../b", "/a\x00"])
def test_a_root_is_an_absolute_path_without_a_climb(root):
    with pytest.raises(ValueError):
        path_within(root)


@pytest.mark.parametrize("language", [PATH, WS], ids=["path", "within"])
def test_draws_and_hazards_are_members_and_outside_values_are_not(language):
    rng = random.Random(0)
    assert all(language.contains(language.sample(rng)) for _ in range(100))
    assert all(language.contains(h.value) for h in language.hazards())
    for seed in range(10):
        outside = language.outside(random.Random(seed))
        assert outside is None or not language.contains(outside)


def test_the_z3_encoding_of_each_pattern_agrees_with_it_on_both_sides():
    z3 = pytest.importorskip("z3")
    from mathema_language import smt
    for language in (PATH, WS, path_within("/")):
        for side in ("older", "newer"):
            enc = smt.MembershipEncoding(z3)
            x = z3.String("x")
            formula = enc.text(language, x, side)
            for text in CASES:
                if "\x00" in text:
                    continue
                solver = z3.Solver()
                solver.add(formula, x == z3.StringVal(text))
                assert (solver.check() == z3.sat) == language.contains(text), (language.name, side, text)


def _copy(**to) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="copy")
    p.add_argument("--to", required=True, **to)
    return p


@pytest.mark.parametrize("parser, verdict, received", [
    (_copy(choices=["out.csv", "reports/q3.csv"]), "proven", None),
    (_copy(choices=["out.csv", "../q3.csv"]), "falsified", "../q3.csv"),
    (_copy(type=Path), "falsified", None),
    (_copy(), "falsified", None),
], ids=["choices-inside", "choices-escape", "any-path", "any-text"])
def test_a_command_line_s_path_option_is_proven_within_the_root_or_falsified(parser, verdict, received):
    pytest.importorskip("z3")
    from mathema_language import smt
    from mathema_language.schema.adaptors.cli_argparse import adapt
    result = smt._field_in(adapt(parser), "to", WS)
    assert result.verdict == verdict, str(result)
    if verdict == "falsified":
        value = smt._received(adapt(parser), result.witness, "to")
        assert not WS.contains(value)
        if received is not None:
            assert value == received
