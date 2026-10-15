# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The argparse adaptor reads a parser, or a function annotated to build
one, as the language of the namespaces `parse_args` returns: one field
per action, read as argparse applies it, and one branch per subcommand.
Every namespace the parser really returns is a member, every drawn
member is one, and a namespace another parser returns is not."""
import argparse
import random
from pathlib import Path

import pytest

from mathema_language.conformance import (
    foreign_object_problems,
    record_adaptor_problems,
)
from mathema_language.schema.adaptors.cli_argparse import adapt, schema_shapes


def handle_sync(args: argparse.Namespace) -> int:
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tool")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument("--color", action=argparse.BooleanOptionalAction)
    parser.add_argument("--mode", choices=["fast", "safe"], default="safe")
    commands = parser.add_subparsers(dest="command")
    sync = commands.add_parser("sync", aliases=["s"])
    sync.add_argument("paths", nargs="+", type=Path)
    sync.add_argument("--retries", type=int, default="3")
    sync.add_argument("--tag", action="append")
    sync.add_argument("--dry-run", dest="dry_run", action="store_const", const="dry")
    sync.set_defaults(handler=handle_sync)
    stat = commands.add_parser("stat")
    stat.add_argument("--ratio", type=float)
    stat.add_argument("pair", nargs=2)
    stat.add_argument("rest", nargs="*")
    return parser


PARSER = build_parser()

ARGVS = [
    [],
    ["-vvv", "--no-color", "--mode", "fast"],
    ["sync", "a.txt"],
    ["s", "a.txt", "b/c", "--retries", "-2", "--tag", "x", "--tag", "", "--dry-run"],
    ["--color", "sync", "--", "-weird name"],
    ["stat", "x", "y"],
    ["stat", "x", "y", "z", "w", "--ratio", "nan"],
    ["stat", "--ratio=-1e308", "x", "y"],
]


def test_passes_the_conformance_checks():
    assert record_adaptor_problems(build_parser, adapt=adapt) == []


def test_returns_none_for_other_objects():
    assert foreign_object_problems(adapt) == []

    def not_a_builder():
        return build_parser()

    assert adapt(not_a_builder) is None


def test_one_shape_per_subcommand_and_one_without():
    assert [s.name for s in schema_shapes(PARSER)] == ["tool", "tool sync", "tool stat"]


@pytest.mark.parametrize("argv", ARGVS, ids=lambda a: " ".join(a) or "(none)")
def test_every_namespace_the_parser_returns_is_a_member(argv):
    namespace = PARSER.parse_args(argv)
    assert adapt(PARSER).explain(namespace) is None, namespace


def test_a_text_default_is_converted_as_argparse_converts_it():
    (sync,) = [s for s in schema_shapes(PARSER) if s.name == "tool sync"]
    (retries,) = [f for f in sync.fields if f.name == "retries"]
    assert retries.default == 3 and retries.type.base == "int"


def test_every_drawn_member_is_a_member():
    language = adapt(PARSER)
    rng = random.Random(3)
    for _ in range(300):
        member = language.sample(rng)
        assert isinstance(member, argparse.Namespace)
        assert language.explain(member) is None, member


def test_a_namespace_from_another_parser_is_not_a_member():
    other = argparse.ArgumentParser()
    other.add_argument("--unrelated")
    assert adapt(PARSER).explain(other.parse_args([])) is not None
    assert adapt(PARSER).explain(argparse.Namespace(command="push")) is not None


def test_a_parser_without_subcommands_is_one_record_language():
    plain = argparse.ArgumentParser()
    plain.add_argument("--n", type=int, required=True)
    language = adapt(plain)
    assert type(language).__name__ == "RowLanguage"
    assert language.explain(plain.parse_args(["--n", "-4"])) is None


def units(args: argparse.Namespace) -> int:
    """Units ordered for a sync, in cases of 12."""
    if args.command == "stat":
        return 0
    return args.verbose * 12


def test_claims_over_the_namespaces():
    from mathema.conjecture import check_conjectures, claim
    (p,) = check_conjectures(units, [claim("for args in L[tests.test_adaptor_argparse.build_parser], f(args) >= 0")])
    assert p.verdict == "holds"


@pytest.mark.parametrize("nargs", ["+", "*", 2])
def test_a_positional_list_is_never_none(nargs):
    p = argparse.ArgumentParser(prog="t")
    p.add_argument("files", nargs=nargs)
    (files,) = adapt(p).schema.fields
    assert not files.nullable
    assert not adapt(p).contains(argparse.Namespace(files=None))


def test_an_optional_list_left_out_is_none():
    p = argparse.ArgumentParser(prog="t")
    p.add_argument("--tag", action="append")
    p.add_argument("--many", nargs="*")
    assert adapt(p).contains(p.parse_args([]))
    assert p.parse_args([]).many is None
