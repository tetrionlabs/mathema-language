# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The alphabet languages: every string over a set of characters, the
empty string included, each with Python's own reading of the alphabet
as its membership test. The hazard sub-alphabets at the end are the
character classes real code mishandles, as languages of their own so a
claim can quantify over exactly them.

Alphabet expressions: a set of characters written as named alphabets
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
(`A-Z`), `lower` (`a-z`) and `hexdigit` (`0-9`, `A-F`, `a-f`), the
hexadecimal digits; the language `L[hex]` is something else, the
strings `bytes.fromhex` reads.

`alphabet_language(expression)` is the language of every string over the
alphabet, the empty string included: membership character by character,
draws written directly from the alphabet, `outside` a member with one
character from outside it, and an exact regular-language term under
`term` in its persisted form. Given a `name` it is a custom
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
import string
import sys
import unicodedata
from dataclasses import dataclass
from typing import Any

from .._surface import HazardValue
from . import _algebra, _regular
from ._algebra import every_string_over
from ._kit import TextLanguage

_ASCII_POOL = string.printable + "\x00\x7f"
_LATIN1_POOL = _ASCII_POOL + "".join(chr(c) for c in range(0x80, 0x100, 5))
_UNICODE_POOL = (_LATIN1_POOL
                 + "\u65e5\u672c\u8a9e\U0001f642\u00e9\u0301\u200b\ufeff"
                 + "\u202e\u0100\u03a9\u0436\u00df\u0130\ufb01")
_LETTERS = string.ascii_letters + "\u00e9\u03a9\u0436\u65e5\u00df\u0130"

_LETTER_CATEGORIES = ("Lu", "Ll", "Lt", "Lm", "Lo")
_NUMBER_CATEGORIES = ("Nd", "Nl", "No")
_MARK_CATEGORIES = ("Mn", "Mc", "Me")
_PUNCTUATION_CATEGORIES = ("Pc", "Pd", "Ps", "Pe", "Pi", "Pf", "Po")
_SYMBOL_CATEGORIES = ("Sm", "Sc", "Sk", "So")
_EVERY_ASSIGNED = (*_LETTER_CATEGORIES, *_NUMBER_CATEGORIES, *_MARK_CATEGORIES,
                   *_PUNCTUATION_CATEGORIES, *_SYMBOL_CATEGORIES,
                   "Zs", "Zl", "Zp", "Cc", "Cf", "Co", "Cs")


def _every_str(s: str) -> bool:
    """Intent:
        Accepts every string, lone surrogates included.
    """
    return True


def _is_ascii(c: str) -> bool:
    """Intent:
        Whether the character `c` is one of the 128 ascii code points.
    """
    return ord(c) < 0x80


def _is_latin1(c: str) -> bool:
    """Intent:
        Whether the character `c` is below U+0100, so the latin-1 codec encodes it.
    """
    return ord(c) < 0x100


def _is_printable(c: str) -> bool:
    """Intent:
        Whether `str.isprintable` accepts the character `c`.
    """
    return c.isprintable()


def _is_digit(c: str) -> bool:
    """Intent:
        Whether the character `c` is one of the ten ascii digits.
    """
    return c in string.digits


def _is_alpha(c: str) -> bool:
    """Intent:
        Whether `str.isalpha` accepts the character `c`, a letter in any script.
    """
    return c.isalpha()


def _is_alnum(c: str) -> bool:
    """Intent:
        Whether `str.isalnum` accepts the character `c`, a letter or digit in any script.
    """
    return c.isalnum()


def _is_c0(c: str) -> bool:
    """Intent:
        Whether the character `c` is a C0 control character or the space, U+0000 to U+0020.
    """
    return ord(c) <= 0x20


def _is_format(c: str) -> bool:
    """Intent:
        Whether the character `c` is in Unicode category Cf, the format characters that show
        nothing.
    """
    return unicodedata.category(c) == "Cf"


def _is_combining(c: str) -> bool:
    """Intent:
        Whether the character `c` is a combining mark, Unicode category Mn, Mc or Me.
    """
    return unicodedata.category(c) in _MARK_CATEGORIES


def _is_surrogate(c: str) -> bool:
    """Intent:
        Whether the character `c` is a surrogate code point, Unicode category Cs.
    """
    return unicodedata.category(c) == "Cs"


def _folds_under_nfkc(c: str) -> bool:
    """Intent:
        Whether NFKC normalisation changes the character `c`.
    """
    return unicodedata.normalize("NFKC", c) != c


def _is_non_bmp(c: str) -> bool:
    """Intent:
        Whether the character `c` lies past U+FFFF, in an astral plane.
    """
    return ord(c) > 0xFFFF


#: every `str`, lone surrogates included: the carrier of text
UNICODE = TextLanguage(
    "unicode", accepts=_every_str, pool=_UNICODE_POOL,
    categories=_EVERY_ASSIGNED, planes=(0, 0, 0, 1, 2, 14, 15, 16),
    schema={"term": every_string_over(((0, 0x10FFFF),), "unicode")})

#: every string over the 128 ascii code points
ASCII = TextLanguage(
    "ascii", char_ok=_is_ascii, pool=_ASCII_POOL,
    outside_pool="\x80\u00e9\u65e5\U0001f642",
    schema={"pattern": "^[\\x00-\\x7f]*$"})

#: every string the latin-1 codec encodes
LATIN1 = TextLanguage(
    "latin-1", char_ok=_is_latin1, pool=_LATIN1_POOL,
    outside_pool="\u0100\u65e5\U0001f642",
    schema={"pattern": "^[\\x00-\\xff]*$"})

#: every string `str.isprintable` accepts
PRINTABLE = TextLanguage(
    "printable", char_ok=_is_printable,
    pool="".join(c for c in _UNICODE_POOL if c.isprintable()),
    categories=(*_LETTER_CATEGORIES, *_NUMBER_CATEGORIES,
                *_PUNCTUATION_CATEGORIES, *_SYMBOL_CATEGORIES, "Zs"),
    planes=(0, 0, 1), outside_pool="\x00\n\x7f\u200b")

#: every string over the ten ascii digits (not `str.isdigit`, which
#: admits the digits of every script and the superscripts)
DIGIT = TextLanguage(
    "digit", char_ok=_is_digit, pool=string.digits, simplest="0",
    outside_pool="a -.\u0663", schema={"pattern": "^[0-9]*$"})

#: every string of ASCII letters
ALPHA = TextLanguage(
    "alpha", char_ok=lambda c: c in string.ascii_letters, pool=string.ascii_letters,
    outside_pool="1 -_\u00e9", schema={"pattern": "^[A-Za-z]*$"})

#: every string of ASCII letters and digits
ALNUM = TextLanguage(
    "alnum", char_ok=lambda c: c in string.ascii_letters or c in string.digits,
    pool=string.ascii_letters + string.digits, outside_pool=" -_.\u00e9",
    schema={"pattern": "^[A-Za-z0-9]*$"})

#: every string of letters in any script, `str.isalpha` character by
#: character
UNICODE_ALPHA = TextLanguage(
    "unicode_alpha", char_ok=_is_alpha, pool=_LETTERS,
    categories=_LETTER_CATEGORIES, planes=(0, 0, 1), outside_pool="1 -_")

#: every string of letters and digits in any script, `str.isalnum`
#: character by character
UNICODE_ALNUM = TextLanguage(
    "unicode_alnum", char_ok=_is_alnum, pool=_LETTERS + string.digits,
    categories=(*_LETTER_CATEGORIES, *_NUMBER_CATEGORIES), planes=(0, 0, 1),
    outside_pool=" -_.")

# the alphabets of characters code usually gets wrong

#: the control characters and the space, 0x00 to 0x20: newlines, NUL
CONTROL = TextLanguage(
    "control", char_ok=_is_c0, pool="".join(chr(c) for c in range(0x21)),
    simplest="\x00", outside_pool="a1")

#: characters that show nothing (Unicode category Cf): zero-width
#: joiners and spaces, the byte-order mark, the bidirectional controls,
#: the tag characters
INVISIBLE = TextLanguage(
    "invisible", char_ok=_is_format, pool="\u200b\u200d\u2060\ufeff\u202e\u202a\u061c",
    categories=("Cf",), planes=(0, 0, 14), simplest="\u200b", outside_pool="a")

#: the combining marks (categories Mn, Mc, Me)
COMBINING = TextLanguage(
    "combining", char_ok=_is_combining, pool="\u0301\u0308\u030a\u0345\u20dd\u0f72",
    categories=_MARK_CATEGORIES, planes=(0, 0, 1), simplest="\u0301",
    outside_pool="a")

#: the surrogate code points, which Python admits in a `str` and no
#: codec encodes
SURROGATE = TextLanguage(
    "surrogate", char_ok=_is_surrogate, pool="\ud800\udbff\udc00\udfff",
    categories=("Cs",), simplest="\ud800", outside_pool="a")

#: the characters whose NFKC form differs from themselves: ligatures,
#: fullwidth forms, superscripts, circled numbers, compatibility ideographs
COMPATIBILITY = TextLanguage(
    "compatibility", char_ok=_folds_under_nfkc,
    pool="\ufb01\u2100\uff03\u00b2\u2460\u3392\ufe13\u01c6\u2160\u33a1",
    simplest="\ufb01", outside_pool="a1")

#: the characters past U+FFFF, the astral planes: most emoji, rarer
#: scripts, two UTF-16 units each
ASTRAL = TextLanguage(
    "astral", char_ok=_is_non_bmp,
    pool="\U0001f642\U0001d120\U00010000\U0001f4a9\U00020000\U0001f3f4",
    categories=(*_LETTER_CATEGORIES, *_SYMBOL_CATEGORIES, *_NUMBER_CATEGORIES),
    planes=(1, 1, 2, 15, 16), simplest="\U00010000", outside_pool="a")


Ranges = tuple[tuple[int, int], ...]

#: the named alphabets, in the order canonical text writes them
NAMES = ("unicode", "ascii", "latin-1", "printable", "unicode_alnum", "unicode_alpha", "alnum",
         "alpha", "upper", "lower", "digit", "hexdigit")

#: the named alphabets this module adds to the registered alphabet languages
_ADDED: dict[str, Ranges] = {
    "upper": ((65, 90),), "lower": ((97, 122),), "hexdigit": ((48, 57), (65, 70), (97, 102))}

_REGISTERED = {"unicode": UNICODE, "ascii": ASCII, "latin-1": LATIN1,
               "printable": PRINTABLE, "unicode_alnum": UNICODE_ALNUM,
               "unicode_alpha": UNICODE_ALPHA, "alnum": ALNUM,
               "alpha": ALPHA, "digit": DIGIT}


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


def _quoted_character(c: str) -> str:
    """Intent:
        One character between double quotes as JSON writes it, with a surrogate code point
        written as its `\\u` escape, since it cannot stand in text by itself.
    """
    return json.dumps(c) if 0xD800 <= ord(c) <= 0xDFFF else json.dumps(c, ensure_ascii=False)


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
        """The canonical text of the expression: each character quoted as
        JSON writes it, a lone surrogate as its escape."""
        return " + ".join([*self.names, *(_quoted_character(c) for c in self.characters)])

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
        return (tuple(_algebra._cs_union(*[low for low, _ in pairs], *own)),
                tuple(_algebra._cs_union(*[high for _, high in pairs], *own)))

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
    return tuple(_algebra._cs_union(*[named_ranges(n) for n in names],
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

    def term(self, version: str | None = None) -> dict[str, Any]:
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
            return _algebra.to_node(_algebra._loop(_algebra._chars_re(ranges), 0, None))

        doc: dict[str, Any] = {
            "kind": "regular_language", "version": _algebra.TERM_VERSION,
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
                "term": self.term()}


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


__all__ = ["ALNUM", "ALPHA", "ASCII", "ASTRAL", "Alphabet", "AlphabetError", "AlphabetLanguage",
           "COMBINING", "COMPATIBILITY", "CONTROL", "DIGIT", "INVISIBLE", "LATIN1", "LOWER",
           "NAMES", "PRINTABLE", "SURROGATE", "UNICODE", "UNICODE_ALNUM", "UNICODE_ALPHA", "UPPER",
           "USERNAME_CHARACTERS", "alphabet", "alphabet_language", "alphabet_refusal",
           "named_ranges", "outside_characters", "parse_alphabet", "plain_character"]
