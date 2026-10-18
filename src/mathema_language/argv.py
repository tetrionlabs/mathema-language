# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The language of the command lines an `argparse.ArgumentParser`
accepts: lists of strings, the `argv` a program's `main` receives.
Membership is the parser's own: a command line is a member when
`parse_args` returns a namespace or ends the program successfully
(`--help`, `--version`), and outside it when the parser refuses it,
explained in the parser's own words.

Members are drawn from the parser's actions, in every spelling argparse
reads the same: `--name value` and `--name=value`, a short option with
its value attached (`-nvalue`), an unambiguous abbreviation (`--verb`
for `--verbose`), short flags combined (`-vq`), options before and after
the positionals, and `--` before a positional that starts with a dash.
Its hazards are the inputs command lines break on: an empty command
line, `--help` on every subcommand, a negative number as a value, an
empty value, a value starting with a dash, a repeated option, an
abbreviation. A parser whose arguments open files (`argparse.FileType`)
is refused, since deciding membership would open them.

Reading a parser also notes the defects argparse accepts without
complaint and that show up only when the program runs: `type=bool`, a
default outside its choices, a text default its type refuses, two
options storing into the same name, choices the type can never
produce, and help text that fails to format. `parser_notes` returns
them, and building either language warns with each one."""
from __future__ import annotations

import argparse
import contextlib
import inspect
import io
import random
import warnings
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from ._surface import DefinedAnswer, HazardValue, Problem, Refusal
from .text import UNICODE

_SKIPPED = (argparse._HelpAction, argparse._VersionAction)
_FLAGS = (argparse._StoreTrueAction, argparse._StoreFalseAction, argparse._StoreConstAction,
          argparse._AppendConstAction, argparse._CountAction)


def _parser_of(obj: Any) -> argparse.ArgumentParser:
    """Intent:
        The parser `obj` is, or the parser `obj` returns when it is a function called with no
        arguments.

    Raises:
        TypeError: `obj` is neither a parser nor a function returning one.
    """
    if isinstance(obj, argparse.ArgumentParser):
        return obj
    if inspect.isfunction(obj):
        built = obj()
        if isinstance(built, argparse.ArgumentParser):
            return built
    raise TypeError(f"not an argparse.ArgumentParser or a function building one: {obj!r}")


def _subparsers(parser: argparse.ArgumentParser) -> argparse._SubParsersAction[argparse.ArgumentParser] | None:
    """Intent:
        The parser's subcommand action, or None when it has no subcommands.
    """
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _all_parsers(parser: argparse.ArgumentParser, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], argparse.ArgumentParser]]:
    """Intent:
        Every parser reachable through subcommands, the given one first, each paired with the
        subcommand words that reach it. A parser named by several aliases appears once.
    """
    out = [(path, parser)]
    sub = _subparsers(parser)
    if sub is not None:
        seen: set[int] = set()
        for name, child in sub.choices.items():
            if id(child) in seen:
                continue
            seen.add(id(child))
            out.extend(_all_parsers(child, (*path, name)))
    return out


def _value(rng: random.Random, action: argparse.Action, plain: bool = False) -> str:
    """Intent:
        One value for the action as command-line text: one of its choices, a number for an int or
        float type, or text that does not start with a dash. With `plain`, the simplest one (the
        first choice, `1`, `a`).
    """
    if action.choices is not None and not isinstance(action, argparse._SubParsersAction):
        return str(next(iter(action.choices))) if plain else str(rng.choice(list(action.choices)))
    if plain:
        return "1" if action.type in (int, float) else "a"
    if action.type is int:
        return str(rng.choice([0, 1, 7, 42, rng.randint(-100, 1000)]))
    if action.type is float:
        return rng.choice(["0", "1.5", "-0.5", "2.0", str(round(rng.uniform(-100, 100), 3))])
    text = UNICODE.sample(rng)
    return text if text and not text.startswith("-") else "value"


def _count(nargs: Any, rng: random.Random) -> int:
    """Intent:
        How many values to draw for an action with this `nargs`: one when it is None, the number
        itself when it is an int, a random count in the range `?`, `*` or `+` allows.
    """
    if nargs is None:
        return 1
    if isinstance(nargs, int):
        return nargs
    return {"?": rng.randint(0, 1), "*": rng.randint(0, 3), "+": rng.randint(1, 3)}.get(nargs, 1)


def _abbreviations(parser: argparse.ArgumentParser, option: str) -> list[str]:
    """Intent:
        The prefixes of a long option, three characters or longer, that name it alone among the
        parser's long options; empty when the parser does not allow abbreviation.
    """
    if not parser.allow_abbrev or not option.startswith("--"):
        return []
    longs = [o for a in parser._actions for o in a.option_strings if o.startswith("--")]
    out = []
    for cut in range(3, len(option)):
        prefix = option[:cut]
        if [o for o in longs if o.startswith(prefix)] == [option]:
            out.append(prefix)
    return out


def _option_tokens(rng: random.Random, parser: argparse.ArgumentParser,
                   action: argparse.Action) -> list[str]:
    """Intent:
        The command-line tokens for one optional action in a random spelling: an abbreviation,
        `--opt=value`, a short option with its value attached, combined count flags, or a repeated
        append.
    """
    options = list(action.option_strings)
    option = rng.choice(options)
    if rng.random() < 0.2:
        option = rng.choice(_abbreviations(parser, option) or [option])
    if isinstance(action, argparse.BooleanOptionalAction):
        return [rng.choice([o for o in options if not o.startswith("--no-")] + [o for o in options if o.startswith("--no-")])]
    if isinstance(action, argparse._CountAction):
        times = rng.randint(1, 3)
        shorts = [o for o in options if len(o) == 2 and o[1] != "-"]
        if shorts and rng.random() < 0.5:
            return ["-" + shorts[0][1] * times]
        return [option] * times
    if isinstance(action, _FLAGS):
        return [option]
    count = _count(action.nargs, rng)
    values = [_value(rng, action) for _ in range(count)]
    repeats = rng.randint(1, 2) if isinstance(action, (argparse._AppendAction, argparse._ExtendAction)) else 1
    tokens: list[str] = []
    for _ in range(repeats):
        if count == 1 and option.startswith("--") and rng.random() < 0.4:
            tokens.append(f"{option}={values[0]}")
        elif count == 1 and len(option) == 2 and rng.random() < 0.3:
            tokens.append(option + values[0])
        else:
            tokens += [option, *values]
    return tokens


def _draw_parser(rng: random.Random, parser: argparse.ArgumentParser) -> list[str]:
    """Intent:
        A random command line for one parser's own arguments: required options always and others
        half the time, in shuffled order, with the positionals after or before them, and `--` before
        a positional starting with a dash.
    """
    optionals: list[list[str]] = []
    positionals: list[str] = []
    for action in parser._actions:
        if isinstance(action, (*_SKIPPED, argparse._SubParsersAction)):
            continue
        if action.option_strings:
            if action.required or rng.random() < 0.5:
                optionals.append(_option_tokens(rng, parser, action))
        else:
            positionals += [_value(rng, action) for _ in range(_count(action.nargs, rng))]
    rng.shuffle(optionals)
    flat = [t for group in optionals for t in group]
    if any(p.startswith("-") for p in positionals):
        return flat + ["--", *positionals]
    if positionals and rng.random() < 0.3:
        return positionals + flat
    return flat + positionals


# ---- notes on the parser itself

class ParserNoteWarning(UserWarning):
    """A defect in a parser that argparse accepts when the parser is
    built."""


@dataclass(frozen=True)
class ParserNote:
    """One defect in a parser: the parser's `prog`, the argument it
    concerns (empty for the parser as a whole), and what goes wrong."""

    prog: str
    argument: str
    message: str

    def __str__(self) -> str:
        noun = "arguments" if ", " in self.argument else "argument"
        where = f"{self.prog}: {noun} {self.argument}" if self.argument else self.prog
        return f"{where}: {self.message}"


def _label(action: argparse.Action) -> str:
    """Intent:
        The name a note gives an action: its option strings joined with `/`, or its `dest` for a
        positional.
    """
    return "/".join(action.option_strings) if action.option_strings else action.dest


def _takes_values(action: argparse.Action) -> bool:
    """Intent:
        Whether the action reads values from the command line, unlike help, version, a flag, a
        boolean option, subcommands or `nargs=0`.
    """
    return not isinstance(action, (*_SKIPPED, *_FLAGS, argparse.BooleanOptionalAction,
                                   argparse._SubParsersAction)) and action.nargs != 0


def _converts(action: argparse.Action) -> bool:
    """Intent:
        Whether the action has a `type` that changes the text it is given (anything callable other
        than `str` and `argparse.FileType`).
    """
    return callable(action.type) and action.type is not str \
        and not isinstance(action.type, argparse.FileType)


def _convert(action: argparse.Action, text: str) -> tuple[bool, Any]:
    """Intent:
        `(True, value)` when the action's type reads `text`, else `(False, the error message)`.
    """
    convert = action.type
    if not callable(convert):
        return False, f"{convert!r} is not callable"
    try:
        return True, convert(text)
    except (TypeError, ValueError, argparse.ArgumentTypeError) as e:
        return False, str(e) or type(e).__name__


def _action_notes(action: argparse.Action) -> list[str]:
    """Intent:
        The defects argparse accepts in one action that takes values: `type=bool`, a text default
        its type refuses, a default outside its choices, and choices its type can never produce.
    """
    if not _takes_values(action):
        return []
    out = []
    if action.type is bool:
        option = action.option_strings[0] if action.option_strings else action.dest
        out.append(f"type=bool reads every non-empty value as True, so `{option} False` "
                   "gives True; a flag is action='store_true' or "
                   "argparse.BooleanOptionalAction")
    default = action.default
    if isinstance(default, str) and _converts(action):
        read, value = _convert(action, default)
        if not read:
            out.append(f"the default {default!r} is not a value its type reads ({value}), so "
                       "every command line that leaves it out is refused")
        else:
            default = value
    if action.choices is not None and default is not None and default is not argparse.SUPPRESS:
        values = default if isinstance(default, (list, tuple)) and action.nargs not in (None, "?") \
            else [default]
        outside = [v for v in values if v not in action.choices]
        if outside:
            out.append(f"the default {action.default!r} is not one of the choices "
                       f"{list(action.choices)!r}, and argparse never checks a default")
    if action.choices is not None and _converts(action):
        never = []
        for choice in action.choices:
            read, value = _convert(action, str(choice))
            if not read or value != choice:
                never.append(choice)
        if never and len(never) == len(list(action.choices)):
            out.append(f"no value is accepted: its type never produces one of the choices "
                       f"{list(action.choices)!r}")
        elif never:
            out.append(f"the choices {never!r} can never be given: its type never produces them")
    return out


def _shared_dests(parser: argparse.ArgumentParser) -> list[ParserNote]:
    """Intent:
        One note per name that several store actions write outside a mutually exclusive group, where
        the last one given wins.
    """
    by_dest: dict[str, list[argparse.Action]] = {}
    for action in parser._actions:
        if type(action) is argparse._StoreAction and action.dest is not argparse.SUPPRESS:
            by_dest.setdefault(action.dest, []).append(action)
    grouped = [set(map(id, g._group_actions)) for g in parser._mutually_exclusive_groups]
    out = []
    for dest, actions in by_dest.items():
        if len(actions) < 2 or any({id(a) for a in actions} <= group for group in grouped):
            continue
        names = ", ".join(_label(a) for a in actions)
        out.append(ParserNote(parser.prog, names,
                              f"all store into {dest!r}, so when more than one is given the last "
                              "one wins silently"))
    return out


def parser_notes(obj: Any) -> list[ParserNote]:
    """The defects in a parser, or a function building one, that argparse
    accepts without complaint, over every subcommand."""
    out: list[ParserNote] = []
    for _path, parser in _all_parsers(_parser_of(obj)):
        for action in parser._actions:
            out += [ParserNote(parser.prog, _label(action), m) for m in _action_notes(action)]
        out += _shared_dests(parser)
        try:
            parser.format_help()
        except (ValueError, TypeError, KeyError) as e:
            out.append(ParserNote(parser.prog, "", f"its help fails to format ({e}), so --help "
                                  "raises instead of printing; a literal % in usage or help is written %%"))
    return out


def warn_parser_notes(notes: list[ParserNote]) -> None:
    """Warn with each note, as a `ParserNoteWarning`."""
    for note in notes:
        warnings.warn(str(note), ParserNoteWarning, stacklevel=3)


class ArgvLanguage:
    """The command lines `parser` accepts. A program refuses a command
    line outside it the way argparse does, with `SystemExit` and exit
    code 2, and answers one inside it with a return or `SystemExit`
    with exit code 0 or 1; `excluded_outside_domain` and
    `is_language_defined` read these."""

    kind = "sequence"
    level = "predicate"
    refusal = Refusal.exit(2)
    defined_answer = DefinedAnswer.exit(0, 1)

    def __init__(self, parser: argparse.ArgumentParser, name: str | None = None) -> None:
        for _path, each in _all_parsers(parser):
            for action in each._actions:
                if isinstance(action.type, argparse.FileType):
                    raise ValueError(f"{each.prog}: argument {action.dest} opens a file "
                                     "(argparse.FileType), so deciding membership would open it")
        self.parser = parser
        self.name = name or f"argv, {parser.prog}"
        self.notes = parser_notes(parser)
        warn_parser_notes(self.notes)

    def __repr__(self) -> str:
        return f"ArgvLanguage({self.parser.prog!r})"

    # ---- membership

    def _parse(self, argv: list[str]) -> str | None:
        """Intent:
            None when the parser accepts `argv` (`--help` and `--version` included), else the
            parser's own error message, the last line it writes to stderr.
        """
        out, err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                self.parser.parse_args(list(argv))
        except SystemExit as e:
            if e.code in (0, None):
                return None
            lines = [line for line in err.getvalue().splitlines() if line.strip()]
            return lines[-1] if lines else f"exit {e.code}"
        except argparse.ArgumentError as e:
            return str(e)
        return None

    def explain(self, value: Any) -> list[Problem] | None:
        if not isinstance(value, (list, tuple)) or not all(isinstance(t, str) for t in value):
            return [Problem("", "a list of str", value)]
        refused = self._parse(list(value))
        return None if refused is None else [Problem("", refused, value)]

    def contains(self, value: Any) -> bool:
        return self.explain(value) is None

    # ---- drawing

    def sample(self, rng: random.Random) -> list[str]:
        for _ in range(40):
            argv = self._draw(rng)
            if self.contains(argv):
                return argv
        return self._simplest()

    def _draw(self, rng: random.Random) -> list[str]:
        """Intent:
            A random command line: the top parser's arguments, then a random subcommand and its
            arguments at each level, stopping one time in five where a subcommand is optional.
        """
        tokens = _draw_parser(rng, self.parser)
        parser = self.parser
        while True:
            sub = _subparsers(parser)
            if sub is None or (not sub.required and rng.random() < 0.2):
                return tokens
            name = rng.choice(list(sub.choices))
            parser = sub.choices[name]
            tokens = tokens + [name] + _draw_parser(rng, parser)

    def _simplest(self, path: tuple[str, ...] | None = None, extra: tuple[str, ...] = ()) -> list[str]:
        """Intent:
            The shortest command line through the subcommands `path` (the first at each level when
            None), with `extra` placed among the last parser's own arguments, before its
            positionals.
        """
        rng = random.Random(0)
        tokens: list[str] = []
        parser = self.parser
        words = list(path) if path is not None else None
        while True:
            options: list[str] = []
            positionals: list[str] = []
            for action in parser._actions:
                if isinstance(action, (*_SKIPPED, argparse._SubParsersAction)):
                    continue
                if action.option_strings and action.required:
                    options += [action.option_strings[0], *([_value(rng, action, plain=True)] * _count(action.nargs, rng))]
                elif not action.option_strings and action.nargs not in ("?", "*"):
                    positionals += [_value(rng, action, plain=True)] * max(1, _count(action.nargs, rng))
            sub = _subparsers(parser)
            last = sub is None or (words is not None and not words) and not sub.required
            if words is not None and not words and sub is not None and sub.required:
                last = False
            if last:
                return tokens + options + list(extra) + positionals
            tokens += options + positionals
            if sub is None:
                return tokens
            name = words.pop(0) if words else next(iter(sub.choices))
            tokens.append(name)
            parser = sub.choices[name]

    def members(self, limit: int) -> tuple[Any, ...] | None:
        return None

    def hazards(self) -> tuple[HazardValue, ...]:
        """The command lines a program most often gets wrong, each one
        kept only if the parser accepts it."""
        out: list[HazardValue] = [HazardValue("empty", [], "an empty command line")]
        for path, parser in _all_parsers(self.parser):
            out.append(HazardValue("text", [*path, "--help"], f"--help on {parser.prog}"))
        for path, parser in _all_parsers(self.parser):
            for action in parser._actions:
                if not action.option_strings \
                        or isinstance(action, (*_SKIPPED, *_FLAGS, argparse.BooleanOptionalAction)):
                    continue
                long = next((o for o in action.option_strings if o.startswith("--")), action.option_strings[0])
                cases: list[tuple[str, tuple[str, ...], str]] = []
                if action.type in (int, float):
                    cases += [("extremity", (long, "-1"), f"{long} -1, a negative number as its value"),
                              ("extremity", (f"{long}=-1",), f"{long}=-1"),
                              ("extremity", (long, "0"), f"{long} 0")]
                if action.type in (None, str):
                    cases += [("empty", (long, ""), f"{long} '', an empty value"),
                              ("text", (f"{long}=-x",), f"{long}=-x, a value starting with a dash"),
                              ("text", (long, "ﬁ"), f"{long} with a ligature as its value")]
                value = "1" if action.type in (int, float) else "x"
                for abbreviation in _abbreviations(parser, long)[:1]:
                    cases.append(("text", (abbreviation, value), f"{abbreviation}, an abbreviation of {long}"))
                cases.append(("duplicate", (long, value, long, value), f"{long} given twice"))
                for kind, extra, note in cases:
                    out.append(HazardValue(kind, self._simplest(path, extra), note))
        kept: list[HazardValue] = []
        seen: list[object] = []
        for hazard in out:
            if hazard.value not in seen and self.contains(hazard.value):
                seen.append(hazard.value)
                kept.append(hazard)
        return tuple(kept)

    def outside(self, rng: random.Random) -> list[str] | None:
        """One command line the parser refuses, near the accepted ones:
        an unknown option, an extra positional, a value of the wrong type
        or outside the choices, a value that starts with a dash, a
        missing required option, each inside its own subcommand."""
        candidates: list[list[str]] = []
        for path, parser in _all_parsers(self.parser):
            base = self._simplest(path)
            candidates += [self._simplest(path, ("--no-such-option",)), [*base, "unexpected-extra-value"]]
            for action in parser._actions:
                if not action.option_strings \
                        or isinstance(action, (*_SKIPPED, *_FLAGS, argparse.BooleanOptionalAction)):
                    continue
                option = action.option_strings[0]
                if action.type in (int, float):
                    candidates.append(self._simplest(path, (option, "not-a-number")))
                    candidates.append(self._simplest(path, (option, "-1e3")))
                if action.choices is not None:
                    candidates.append(self._simplest(path, (option, "<not a choice>")))
                candidates.append(self._simplest(path, (option, "-x")))
                if action.required:
                    candidates.append([t for t in base if t not in action.option_strings])
        rng.shuffle(candidates)
        for candidate in candidates:
            if not self.contains(candidate):
                return candidate
        return None

    def shrink(self, value: Any) -> Iterable[Any]:
        """Shorter command lines that are still members: a token left
        out, a value cut to its first character."""
        if not isinstance(value, list):
            return ()
        out: list[list[str]] = []
        for i in range(len(value)):
            out.append(value[:i] + value[i + 1:])
            if i + 1 < len(value):
                out.append(value[:i] + value[i + 2:])
        for i, token in enumerate(value):
            if len(token) > 1 and not token.startswith("-"):
                out.append([*value[:i], token[:1], *value[i + 1:]])
        return [c for c in out if self.contains(c)]

    def fields(self) -> dict[str, Any] | None:
        return None

    def render(self, ascii_mode: bool = True) -> str:
        return f"L[{self.name}]"

    def to_json(self) -> dict[str, Any]:
        return {"type": "array", "items": {"type": "string"},
                "x-mathema": {"argv": self.parser.prog}}


def argv_language(obj: Any) -> ArgvLanguage:
    """The command lines a parser accepts, for a parser or a function of
    no arguments that builds one."""
    return ArgvLanguage(_parser_of(obj))


__all__ = ["ArgvLanguage", "ParserNote", "ParserNoteWarning", "argv_language", "parser_notes"]
