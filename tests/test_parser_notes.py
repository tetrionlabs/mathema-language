# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Reading a parser notes the defects argparse accepts when the parser
is built. Each note is checked against what argparse then does with a
command line, so a note states a behaviour rather than a style
preference; the parsers in the examples have none, nor do the patterns
argparse intends (a store_true and store_false pair on one name,
alternatives in a mutually exclusive group); and building either
language warns with each note."""
import argparse
import contextlib
import io
import sys
from pathlib import Path

import pytest

from mathema_language.argv import ParserNoteWarning, argv_language, parser_notes
from mathema_language.schema.adaptors import cli_argparse
from tests.test_adaptor_argparse import build_parser as tool_parser

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
if str(EXAMPLES) not in sys.path:
    sys.path.insert(0, str(EXAMPLES))

from shop import admin  # noqa: E402


def parser(prog: str = "p") -> argparse.ArgumentParser:
    return argparse.ArgumentParser(prog=prog)


def parse(p: argparse.ArgumentParser, argv: list[str]) -> argparse.Namespace | int:
    """The namespace, or the exit code when the parser ends the program."""
    with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
        try:
            return p.parse_args(argv)
        except SystemExit as e:
            return int(e.code or 0)


def messages(p: argparse.ArgumentParser) -> list[str]:
    return [str(n) for n in parser_notes(p)]


def test_type_bool_reads_false_as_true():
    p = parser()
    p.add_argument("--flag", type=bool)
    assert parse(p, ["--flag", "False"]).flag is True
    [note] = parser_notes(p)
    assert note.argument == "--flag" and "type=bool" in note.message


def test_a_default_outside_its_choices():
    p = parser()
    p.add_argument("--mode", choices=["fast", "safe"], default="slow")
    assert parse(p, []).mode == "slow"
    assert parse(p, ["--mode", "slow"]) == 2
    [note] = messages(p)
    assert "'slow' is not one of the choices" in note


def test_a_text_default_its_type_refuses():
    p = parser()
    p.add_argument("--n", type=int, default="ten")
    p.add_argument("name")
    assert parse(p, ["x"]) == 2
    assert parse(p, ["--n", "3", "x"]).n == 3
    [note] = messages(p)
    assert "'ten' is not a value its type reads" in note


def test_a_text_default_its_type_reads_is_compared_after_conversion():
    p = parser()
    p.add_argument("--n", type=int, choices=[1, 2], default="2")
    assert parse(p, []).n == 2
    assert parser_notes(p) == []


def test_two_options_storing_into_one_name():
    p = parser()
    p.add_argument("--out")
    p.add_argument("--output", dest="out")
    assert parse(p, ["--out", "a", "--output", "b"]).out == "b"
    [note] = messages(p)
    assert note.startswith("p: arguments --out, --output: all store into 'out'")


def test_choices_the_type_never_produces():
    p = parser()
    p.add_argument("--k", type=int, choices=["1", "2"])
    assert parse(p, ["--k", "1"]) == 2
    assert parse(p, ["--k", "2"]) == 2
    [note] = messages(p)
    assert "no value is accepted" in note


def test_one_choice_the_type_never_produces():
    p = parser()
    p.add_argument("--case", type=str.lower, choices=["a", "B"])
    assert parse(p, ["--case", "A"]).case == "a"
    assert parse(p, ["--case", "B"]) == 2
    [note] = messages(p)
    assert "the choices ['B'] can never be given" in note


def test_help_that_fails_to_format():
    p = parser()
    p.add_argument("--share", help="share in %")
    with pytest.raises(ValueError):
        parse(p, ["--help"])
    [note] = parser_notes(p)
    assert note.argument == "" and "%%" in note.message


def test_notes_reach_every_subcommand():
    p = parser("tool")
    sub = p.add_subparsers(dest="command")
    run = sub.add_parser("run", aliases=["r"])
    run.add_argument("--retries", type=int, default="three")
    [note] = messages(p)
    assert note.startswith("tool run: argument --retries")


def test_the_patterns_argparse_intends_have_no_notes():
    p = parser()
    p.add_argument("-v", dest="verbose", action="store_true")
    p.add_argument("-q", dest="verbose", action="store_false")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--json", dest="fmt")
    group.add_argument("--csv", dest="fmt")
    p.add_argument("--tag", action="append")
    p.add_argument("--label", action="append", dest="tag")
    p.add_argument("--level", type=int, choices=range(1, 4), default=2)
    p.add_argument("--rate", type=float, default="0.5")
    p.add_argument("--share", help="share in %%")
    assert parser_notes(p) == []


@pytest.mark.parametrize("build", [admin.build_parser, tool_parser], ids=["shop", "tool"])
def test_the_example_parsers_have_no_notes(build):
    assert parser_notes(build) == []


def test_both_languages_warn_with_each_note():
    p = parser()
    p.add_argument("--flag", type=bool)
    with pytest.warns(ParserNoteWarning, match="type=bool"):
        language = argv_language(p)
    assert [n.argument for n in language.notes] == ["--flag"]
    with pytest.warns(ParserNoteWarning, match="type=bool"):
        cli_argparse.adapt(p)
