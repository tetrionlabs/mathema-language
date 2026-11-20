# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Alphabet expressions: a set of characters written as named alphabets
and single characters joined by `+`, and the language of every string
over it.

`lower + digit + "_"` is the lower-case ASCII letters, the ASCII digits
and the underscore. A part is the name of an alphabet or a quoted
character; a quoted string of several characters is read as each of its
characters. The canonical text names the alphabets first, in the fixed
order of `NAMES`, then the characters in code point order, each in its
own double quotes as JSON writes it, every part once: `"_" + digit + "ab" + lower` is
written `lower + digit + "_" + "a" + "b"`.

The named alphabets are the alphabet languages this package registers
(`unicode`, `ascii`, `latin-1`, `printable`, `unicode_alnum`,
`unicode_alpha`, `alnum`, `alpha`, `digit`) and three more: `upper`
(`A-Z`), `lower` (`a-z`) and `hex` (`0-9`, `A-F`, `a-f`). In an alphabet
expression `hex` is the set of hexadecimal digits, one character; the
language `L[hex]` is something else, the strings `bytes.fromhex` reads.

`alphabet_language(expression)` is the language of every string over the
alphabet, the empty string included: membership character by character,
draws written directly from the alphabet, `outside` a member with one
character from outside it, and an exact regular-language term under
`definition` in its persisted form. Given a `name` it is a custom
alphabet: defined once in code, named in a claim by its dotted path
(`L[myapp.USERNAME_CHARS, len in [3, 32]]`), and kept fresh in a record
by the hash of its term.
"""
from __future__ import annotations

import ast
import bisect
import difflib
import functools
import json
import random
import re
import sys
from dataclasses import dataclass
from typing import Any

from .._surface import HazardValue
from . import _regular
from . import alphabets as _alphabets
from ._kit import TextLanguage

Ranges = tuple[tuple[int, int], ...]

#: the named alphabets, in the order canonical text writes them
NAMES = ("unicode", "ascii", "latin-1", "printable", "unicode_alnum", "unicode_alpha", "alnum",
         "alpha", "upper", "lower", "digit", "hex")

#: the named alphabets this module adds to the registered alphabet languages
_ADDED: dict[str, Ranges] = {
    "upper": ((65, 90),), "lower": ((97, 122),), "hex": ((48, 57), (65, 70), (97, 102))}

_REGISTERED = {"unicode": _alphabets.UNICODE, "ascii": _alphabets.ASCII, "latin-1": _alphabets.LATIN1,
               "printable": _alphabets.PRINTABLE, "unicode_alnum": _alphabets.UNICODE_ALNUM,
               "unicode_alpha": _alphabets.UNICODE_ALPHA, "alnum": _alphabets.ALNUM,
               "alpha": _alphabets.ALPHA, "digit": _alphabets.DIGIT}


class AlphabetError(ValueError):
    """An alphabet expression that does not read, with what was expected
    and the position, counted from 0, where it was expected."""

    def __init__(self, expression: str, position: int, expected: str, found: str) -> None:
        self.expression, self.position, self.expected, self.found = expression, position, expected, found
        super().__init__(f"alphabet {expression!r}: expected {expected} at position {position}, "
                         f"found {found}")


@functools.cache
def named_ranges(name: str) -> Ranges:
    """Intent:
        The code points of a named alphabet, as sorted, disjoint, inclusive ranges.

    Raises:
        ValueError: `name` is not one of `NAMES`.
    """
    if name in _ADDED:
        return _ADDED[name]
    if name not in _REGISTERED:
        raise ValueError(f"a named alphabet is one of {', '.join(NAMES)}, not {name!r}")
    if name == "unicode":
        return ((0, sys.maxunicode),)
    test = _REGISTERED[name].char_ok
    assert test is not None
    runs: list[list[int]] = []
    for code in range(sys.maxunicode + 1):
        if test(chr(code)):
            if runs and runs[-1][1] == code - 1:
                runs[-1][1] = code
            else:
                runs.append([code, code])
    return tuple((lo, hi) for lo, hi in runs)


#: what a named alphabet that depends on the Unicode version holds, in words
_VERSIONED = {"printable": "printable characters", "unicode_alnum": "letters and digits",
              "unicode_alpha": "letters"}


def _named_bounds(name: str, version: str | None = None) -> tuple[Ranges, Ranges]:
    """Intent:
        The code points of a named alphabet as a pair: on every supported Python, those every
        version holds and those any version holds or a later one may (the unassigned); for
        one `version`, that version's set twice. One set for an alphabet that does not depend
        on the Unicode version.

    Raises:
        ValueError: `name` is not one of `NAMES`, or `version` not a supported Python.
    """
    if name in _VERSIONED:
        low, high = _regular.class_bounds(name, version)
        return tuple(low), tuple(high)
    return named_ranges(name), named_ranges(name)


@dataclass(frozen=True)
class Alphabet:
    """A set of characters: the union of the named alphabets `names`
    and the single characters `characters`, held in canonical order
    (names as in `NAMES`, characters by code point, each once). Adding
    an alphabet gives the union; adding a string adds each of its
    characters."""
    names: tuple[str, ...] = ()
    characters: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in self.names:
            named_ranges(name)
        if any(not isinstance(c, str) or len(c) != 1 for c in self.characters):
            raise ValueError("an alphabet's characters are single characters")
        if not self.names and not self.characters:
            raise ValueError("an alphabet holds at least one named alphabet or character")
        object.__setattr__(self, "names", tuple(n for n in NAMES if n in self.names))
        object.__setattr__(self, "characters", tuple(sorted(set(self.characters))))

    @property
    def text(self) -> str:
        """The canonical text of the expression."""
        return " + ".join([*self.names, *(json.dumps(c, ensure_ascii=False) for c in self.characters)])

    @property
    def ranges(self) -> Ranges:
        """The code points of the alphabet, as sorted, disjoint,
        inclusive ranges."""
        return _ranges(self.names, self.characters)

    @property
    def bounds(self) -> tuple[Ranges, Ranges]:
        """The alphabet on every supported Python: the code points every
        version holds, and those any version holds or may come to."""
        return self.bounds_on(None)

    def bounds_on(self, version: str | None) -> tuple[Ranges, Ranges]:
        """The alphabet on one Python `version` (its set twice), or,
        with None, on every supported Python as `bounds` gives it."""
        own = tuple(((ord(c), ord(c)),) for c in self.characters)
        pairs = [_named_bounds(n, version) for n in self.names]
        return (tuple(_regular._cs_union(*[low for low, _ in pairs], *own)),
                tuple(_regular._cs_union(*[high for _, high in pairs], *own)))

    @property
    def varying(self) -> tuple[str, ...]:
        """What the alphabet holds that differs between Python versions,
        in words."""
        return tuple(_VERSIONED[n] for n in self.names if n in _VERSIONED)

    def has(self, ch: str) -> bool:
        """Whether the one character `ch` is in the alphabet."""
        ranges = self.ranges
        at = bisect.bisect_right(ranges, (ord(ch), sys.maxunicode + 1)) - 1
        return at >= 0 and ranges[at][0] <= ord(ch) <= ranges[at][1]

    def __add__(self, other: object) -> Alphabet:
        if isinstance(other, Alphabet):
            return Alphabet(self.names + other.names, self.characters + other.characters)
        if isinstance(other, str) and other:
            return Alphabet(self.names, self.characters + tuple(other))
        return NotImplemented

    def __radd__(self, other: object) -> Alphabet:
        return self.__add__(other)


@functools.lru_cache(maxsize=512)
def _ranges(names: tuple[str, ...], characters: tuple[str, ...]) -> Ranges:
    """Intent:
        The union of the named alphabets and the characters, as sorted, disjoint, inclusive,
        non-adjacent ranges.
    """
    return tuple(_regular._cs_union(*[named_ranges(n) for n in names],
                                    *[((ord(c), ord(c)),) for c in characters]))


_PART = re.compile(r"""\s*(?:(?P<name>[A-Za-z][A-Za-z0-9_-]*)|"(?P<double>(?:[^"\\]|\\.)*)"|'(?P<single>(?:[^'\\]|\\.)*)')\s*""",
                   re.DOTALL)


def parse_alphabet(expression: str) -> Alphabet:
    """Intent:
        The alphabet an expression states: named alphabets and quoted characters joined by
        `+`. Quotes are double or single and what stands between them is read as a Python
        string, so `"\\n"` is a newline and `"\\""` a double quote; a quoted string of several
        characters is each of its characters.

    Raises:
        AlphabetError: the expression does not read, names an alphabet that is not one of
            `NAMES` (the nearest name is offered), or quotes no character.
    """
    names: list[str] = []
    characters: list[str] = []
    at = 0
    while True:
        found = _PART.match(expression, at)
        if found is None:
            where = at + len(expression[at:]) - len(expression[at:].lstrip())
            raise AlphabetError(expression, where, 'the name of an alphabet or a quoted character',
                                '"' + expression[where:where + 8] + '"' if where < len(expression)
                                else "the end of the expression")
        if found.group("name") is not None:
            name = found.group("name")
            if name not in NAMES:
                near = difflib.get_close_matches(name, NAMES, n=1)
                raise AlphabetError(expression, found.start("name"),
                                    "a named alphabet (" + ", ".join(NAMES) + ")",
                                    f'"{name}"' + (f"; did you mean {near[0]}?" if near else ""))
            names.append(name)
        else:
            group = "double" if found.group("double") is not None else "single"
            try:
                inside = ast.literal_eval(expression[found.start(group) - 1:found.end(group) + 1])
            except (ValueError, SyntaxError):
                inside = None
            if not isinstance(inside, str):
                raise AlphabetError(expression, found.start(group) - 1, "a quoted character",
                                    '"' + expression[found.start(group) - 1:found.end(group) + 1] + '"')
            if inside == "":
                raise AlphabetError(expression, found.start(group), "a character between the quotes",
                                    "nothing")
            characters += list(inside)
        at = found.end()
        if at >= len(expression):
            return Alphabet(tuple(names), tuple(characters))
        if expression[at] != "+":
            raise AlphabetError(expression, at, '"+" between the parts', '"' + expression[at] + '"')
        at += 1


def alphabet(expression: Any) -> Alphabet:
    """The alphabet `expression` states: an `Alphabet` itself, or the
    text of an alphabet expression (`'lower + digit + "_"'`).

    Raises:
        AlphabetError: the text does not read as an alphabet expression.
        ValueError: `expression` is neither.
    """
    if isinstance(expression, Alphabet):
        return expression
    if isinstance(expression, str):
        return parse_alphabet(expression)
    raise ValueError(f"an alphabet is an alphabet expression, not {expression!r}")


def _pool(found: Alphabet, limit: int = 160) -> str:
    """Intent:
        Up to `limit` characters of the alphabet to draw from: the ASCII ones first, then the
        start of each further range.
    """
    out: list[str] = []
    for lo, hi in found.ranges:
        for code in range(lo, min(hi, 127) + 1):
            out.append(chr(code))
    for lo, hi in found.ranges:
        for code in range(max(lo, 128), min(hi, max(lo, 128) + 2) + 1):
            if len(out) < limit:
                out.append(chr(code))
    return "".join(out[:limit])


def outside_characters(found: Alphabet) -> str:
    """Intent:
        Characters just outside the alphabet: the code points beside each of its ranges, and a
        space, a newline, an underscore, a digit, a letter and a letter outside ASCII where
        the alphabet does not hold them. Empty when the alphabet is every character.
    """
    out: list[str] = []
    for lo, hi in found.ranges[:4]:
        out += [chr(c) for c in (lo - 1, hi + 1) if 0 <= c <= sys.maxunicode]
    out += [" ", "\n", "_", "0", "a", "A", "é"]
    return "".join(dict.fromkeys(c for c in out if not found.has(c)))


def plain_character(found: Alphabet) -> str:
    """Intent:
        The plainest character of the alphabet: `a`, `A` or `0` when it holds one, else its
        first.
    """
    for ch in "aA0":
        if found.has(ch):
            return ch
    return chr(found.ranges[0][0])


@dataclass(frozen=True)
class AlphabetLanguage(TextLanguage):
    """Every string over an alphabet, the empty string included."""
    alphabet: Alphabet | None = None

    def sample(self, rng: random.Random) -> str:
        assert self.alphabet is not None
        n = rng.choice([0, 1, 1, 2, 3, 5, 8, 13, rng.randint(0, 40)])
        ranges = self.alphabet.ranges

        def one() -> str:
            if rng.random() < 0.8 and self.pool:
                return rng.choice(self.pool)
            lo, hi = rng.choice(ranges)
            return chr(rng.randint(lo, hi))
        return "".join(one() for _ in range(n))

    def outside(self, rng: random.Random) -> Any:
        if not self.outside_pool:
            return None
        inside = self.sample(rng)
        at = rng.randint(0, len(inside))
        return inside[:at] + rng.choice(self.outside_pool) + inside[at:]

    def definition(self, version: str | None = None) -> dict[str, Any]:
        """The regular-language term of the language, any number of
        characters of the alphabet, the same on every supported Python:
        exact, or, for an alphabet whose characters depend on the Unicode
        version, the pair of bounds that holds on all of them. With a
        `version` (`"3.13"`), that Python's reading, exact."""
        assert self.alphabet is not None
        low, high = self.alphabet.bounds_on(version)
        data = _regular.versions_data()
        covered = list(data["versions"]) if version is None else [version]

        def every(ranges: Ranges) -> dict[str, Any]:
            return _regular.to_node(_regular._loop(_regular._chars_re(ranges), 0, None))

        doc: dict[str, Any] = {
            "kind": "regular_language", "version": _regular.TERM_VERSION,
            "alphabet": [[0, sys.maxunicode]], "exact": low == high,
            "source": {"dialect": "alphabet", "alphabet": self.alphabet.text,
                       "versions": covered,
                       "unicode": list(dict.fromkeys(data["unicode"][v] for v in covered))}}
        if low == high:
            doc["language"] = every(low)
        else:
            doc["at_least"], doc["at_most"] = every(high), every(low)
            doc["source"]["not_exact"] = [f"{what}, which differ slightly between Python versions"
                                          for what in self.alphabet.varying]
        return doc

    def to_json(self) -> dict[str, Any]:
        assert self.alphabet is not None
        return {**super().to_json(),
                "alphabet": {"names": list(self.alphabet.names),
                             "characters": list(self.alphabet.characters)},
                "definition": self.definition()}


def alphabet_language(expression: Any, name: str | None = None) -> AlphabetLanguage:
    """The language of every string over an alphabet, the empty string
    included. `expression` is an `Alphabet` or the text of an alphabet
    expression; `name` names a custom alphabet, and without it the
    language is named by the expression's canonical text.

    Raises:
        AlphabetError: the text does not read as an alphabet expression.
        ValueError: `expression` is neither an alphabet nor text.
    """
    found = alphabet(expression)
    pool = _pool(found)
    edges = "".join(dict.fromkeys(chr(c) for lo, hi in found.ranges[:6] for c in (lo, hi)))
    hazards = (HazardValue("text", "", "the empty string"),
               *(HazardValue("text", c, "one character at the edge of the alphabet") for c in edges),
               HazardValue("text", edges, "the characters at the edges of the alphabet"))
    return AlphabetLanguage(
        name or found.text, level="alphabet", char_ok=found.has, pool=pool,
        outside_pool=outside_characters(found), simplest=plain_character(found),
        extra_hazards=hazards, alphabet=found)


#: every string of lower-case ASCII letters
LOWER = alphabet_language("lower")

#: every string of upper-case ASCII letters
UPPER = alphabet_language("upper")

#: a custom alphabet, as a project defines one: the characters of a user name
USERNAME_CHARACTERS = alphabet_language('lower + digit + "_"', name="username characters")


def alphabet_refusal(expression: str) -> str | None:
    """Intent:
        Why `expression` is refused as an alphabet expression, or None when it reads: what was
        expected and where, with the nearest named alphabet for a name that is not one.
    """
    try:
        parse_alphabet(expression)
    except ValueError as e:
        return str(e)
    return None


__all__ = ["LOWER", "NAMES", "UPPER", "USERNAME_CHARACTERS", "Alphabet", "AlphabetError",
           "AlphabetLanguage", "alphabet", "alphabet_language", "alphabet_refusal", "named_ranges",
           "outside_characters", "parse_alphabet", "plain_character"]
