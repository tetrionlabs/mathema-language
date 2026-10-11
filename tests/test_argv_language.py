# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The command lines a parser accepts are a language: every drawn
command line is accepted by the parser, every value just outside is
refused in the parser's own words, the hazards (an empty command line,
`--help` on every subcommand, a negative number, an empty value, an
abbreviation, a repeated option) are all accepted, shrinking keeps
membership, and a parser whose arguments open files is refused. A
function over command lines is claimed through a registered name."""
import argparse
import random
import sys
from pathlib import Path

import mathema.languages as languages
import pytest

from mathema_language.argv import ArgvLanguage, argv_language
from tests.test_adaptor_argparse import build_parser as tool_parser

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
if str(EXAMPLES) not in sys.path:
    sys.path.insert(0, str(EXAMPLES))

from shop import admin  # noqa: E402


def plain_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plain")
    parser.add_argument("--n", type=int, default=1)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument("names", nargs="*")
    return parser


PARSERS = {"shop": admin.build_parser, "tool": tool_parser, "plain": plain_parser}


@pytest.mark.parametrize("name", PARSERS)
def test_it_is_a_language_mathema_accepts(name):
    assert languages.language_problems(argv_language(PARSERS[name])) == []


@pytest.mark.parametrize("name", PARSERS)
def test_every_drawn_command_line_is_accepted(name):
    language = argv_language(PARSERS[name])
    rng = random.Random(5)
    for _ in range(300):
        argv = language.sample(rng)
        assert isinstance(argv, list) and all(isinstance(t, str) for t in argv)
        assert language.contains(argv), argv


@pytest.mark.parametrize("name", PARSERS)
def test_every_outside_value_is_refused_in_the_parsers_words(name):
    language = argv_language(PARSERS[name])
    rng = random.Random(6)
    for _ in range(40):
        argv = language.outside(rng)
        assert argv is not None
        (problem,) = language.explain(argv)
        assert "error:" in problem.predicate, problem


def test_the_hazards_are_the_ones_command_lines_break_on():
    language = argv_language(admin.build_parser)
    notes = {h.note: h.value for h in language.hazards()}
    assert notes["--help on shop restock"] == ["restock", "--help"]
    assert notes["--quantity -1, a negative number as its value"] == ["restock", "--quantity", "-1", "a"]
    assert notes["--q, an abbreviation of --quantity"] == ["restock", "--q", "1", "a"]
    assert all(language.contains(h.value) for h in language.hazards())
    assert argv_language(plain_parser).hazards()[0].value == []


def test_refusals_and_successful_exits():
    language = argv_language(admin.build_parser)
    assert language.contains(["--help"]) and language.contains(["discount", "--help"])
    (problem,) = language.explain(["restock", "--quantity", "x", "a"])
    assert problem.predicate == "shop restock: error: argument --quantity: invalid int value: 'x'"
    assert language.explain("restock a") == [languages.Problem("", "a list of str", "restock a")]


def test_shrinking_keeps_membership():
    language = argv_language(tool_parser)
    rng = random.Random(7)
    for _ in range(30):
        argv = language.sample(rng)
        assert all(language.contains(c) for c in language.shrink(argv))


def test_a_parser_that_opens_files_is_refused():
    parser = argparse.ArgumentParser(prog="reads")
    parser.add_argument("source", type=argparse.FileType("r"))
    with pytest.raises(ValueError, match="opens a file"):
        ArgvLanguage(parser)


def units_from_argv(argv: list[str]) -> int:
    """How many units the admin command line orders, 0 for help."""
    try:
        args = admin.build_parser().parse_args(argv)
    except SystemExit:
        return 0
    return admin.units_ordered(args)


def test_a_claim_over_command_lines_finds_the_negative_order():
    from mathema.conjecture import check_conjectures, claim
    languages.register_language("shop_admin_argv", argv_language(admin.build_parser))
    (p,) = check_conjectures(units_from_argv, [claim("for argv in L[shop_admin_argv], f(argv) >= 0")])
    assert p.verdict == "falsified"
    assert p.counterexample.startswith("argv = ['restock', '--quantity', '-1', 'a']")
