# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Shapes: text pictured one character at a time.

A shape is a picture of the text it admits, read left to right.

- Every letter and every digit in a picture is a symbol and stands for
  one character of one class. Four are built in: `A` a letter, `a` a
  lower-case letter, `9` a digit, `X` any one character. Any other must
  be bound to an alphabet after the picture, and a letter or digit that
  is neither is refused, with both ways to mend it: quote it, or bind
  it.
- Literal text goes in single quotes: `'INV-'9{4}`. Inside the quotes
  every character is itself and a doubled single quote is one single
  quote.
- Punctuation and spaces outside quotes are themselves, and a backslash
  makes the next character itself (`\\[` a bracket, `\\'` a quote).
- `[ ... ]` is an optional part, and may hold optional parts.
- A count follows a symbol, a character, a quoted text or a bracket
  group: `{n}` exactly n, `{n,m}` from n to m, `{n+}` n or more. After
  quoted text it counts the whole text. A counted group is no longer
  optional by itself: `[-99]{2}` is the part twice, `[-99]{0,2}` up to
  twice.

`AA99[ ]9AA` is two letters, two digits, an optional space, a digit and
two letters. The notation is a strict subset of regular expressions with
no alternation and no anchors, in which every position names its class,
so members and near misses are written down directly, never searched
for.

A binding gives a symbol an alphabet (`mathema_language.text.alphabet`):
`Shape("AW{0+}", W='alnum + "_"')` is a letter, then any number of
letters, digits and underscores. A binding may give a built-in symbol
another alphabet for that one shape (`Shape("AA99", A="upper")`), which
is seen in the bindings written after the picture; a binding the picture
never uses is refused.

What an unbound letter and digit are follows the base language. Over
`ascii`: `A` is `A-Z` and `a-z`, `a` is `a-z`, `9` is `0-9`, `X` is any
ASCII character. Over `unicode`: `A` is any character of a Unicode
letter category (`L*`, what `str.isalpha` accepts of one character),
`a` any lower-case letter (category `Ll`), `9` any decimal digit
(category `Nd`, what `\\d` matches), `X` any character at all, a
newline included. Over `ascii` a bound alphabet holds ASCII characters
only.

A shape states itself four ways that agree: `matches`, its own reading
of the picture; `pattern`, an equivalent Python regular expression to be
read in full, made of literals, character classes, `(?:...)` groups and
counts only; `term`, the regular-language term, always exact; and its
canonical text. The canonical picture is the picture as written with
these changes: a backslash before a character that needs none is
dropped; `{n,n}` is written `{n}`; a count that changes nothing (`{1}`,
or `{0,1}` after a group) is dropped; quoted text with no letter or
digit loses its quotes; and letters and digits written with backslashes
become quoted text, joined with quoted text beside them. The bindings
follow, sorted by symbol, each alphabet in its own canonical order.

`Shape` is also the marker for a record field,
`Annotated[str, Shape("AA99[ ]9AA", "ascii")]`: the dataclass, TypedDict
and pydantic adaptors read its `pattern` into the field's regular
expression constraint, and a pydantic model validates the field with the
shape itself.

`SHAPE` is the word's own description, for a registry: the base
languages it has a meaning for, an example for each, and
`suggest_shape`, which guesses the claim that was meant when a use is
refused.
"""
from __future__ import annotations

import functools
import random
import re
import sys
import unicodedata
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from .._surface import HazardValue
from . import _regular
from ._kit import TextLanguage
from .alphabet import Alphabet, alphabet, outside_characters, plain_character
from .alphabets import ASCII, UNICODE

#: the built-in symbols and what each stands for
SYMBOLS = {"A": "a letter", "a": "a lower-case letter", "9": "a digit", "X": "any one character"}

#: the punctuation a picture writes with a backslash to mean itself
_ESCAPED = "[]{}\\'"

#: the base languages a shape reads its classes from
BASES = ("ascii", "unicode")


class ShapeError(ValueError):
    """A shape that does not read, with what was expected and the
    position, counted from 0, where it was expected."""

    def __init__(self, shape: str, position: int, expected: str, found: str) -> None:
        self.shape, self.position, self.expected, self.found = shape, position, expected, found
        super().__init__(f"shape {shape!r}: expected {expected} at position {position}, found {found}")


def _and(parts: list[str]) -> str:
    """Intent:
        The parts as an English list ending in `and`.
    """
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


class UnknownSymbol(ShapeError):
    """A picture holding letters or digits that are neither built-in
    symbols nor bound. `symbols` are those characters in the order
    written, `quoted` the picture with each run of them quoted as
    literal text, and `bindings` the bindings given, as written after a
    picture. The message offers both ways to mend it."""

    def __init__(self, shape: str, position: int, symbols: tuple[str, ...], runs: tuple[str, ...],
                 quoted: str, bindings: str) -> None:
        ShapeError.__init__(self, shape, position, "a symbol (A, a, 9, X or a bound one), quoted text "
                            "or punctuation", '"' + symbols[0] + '"')
        self.symbols, self.runs, self.quoted, self.bindings = symbols, runs, quoted, bindings
        names = _and(list(symbols))
        self.args = (
            f"{names} {'is not a symbol' if len(symbols) == 1 else 'are not symbols'}. "
            f"For the literal text write {_and([_run_text(r) for r in runs])}: "
            f"shape ({_quoted(quoted)}{bindings}). "
            f"To use {symbols[0]} as a symbol, bind it: "
            f"shape ({_quoted(shape)}{bindings}, {symbols[0]} = ...)",)


@dataclass(frozen=True)
class _Class:
    """One character of the class a symbol names."""
    symbol: str


@dataclass(frozen=True)
class _Literal:
    """One given character, written bare or after a backslash."""
    char: str


@dataclass(frozen=True)
class _Run:
    """Quoted text: its characters in order."""
    text: str


@dataclass(frozen=True)
class _Group:
    """A bracketed part: its items in order."""
    items: tuple[Any, ...]


@dataclass(frozen=True)
class _Item:
    """An atom (a class, a character, quoted text or a group) taken from
    `lo` to `hi` times, `hi` None for no upper bound."""
    atom: Any
    lo: int
    hi: int | None


def _quoted(text: str) -> str:
    """Intent:
        `text` between double quotes, as an argument is written inside a predicate's brackets:
        a backslash and a double quote each take a backslash before them.
    """
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _run_text(text: str) -> str:
    """Intent:
        `text` as quoted text in a picture: between single quotes, a single quote doubled.
    """
    return "'" + text.replace("'", "''") + "'"


def _count(shape: str, at: int) -> tuple[int, int | None, int]:
    """Intent:
        The count written at position `at` of `shape`, which holds a `{`: its lower bound, its
        upper bound (None for `{n+}`), and the position after its `}`.

    Raises:
        ShapeError: the text there is not `{n}`, `{n,m}` or `{n+}`, or its bounds admit
            nothing (`m` below `n`, or `m` zero).
    """
    found = re.compile(r"\{([0-9]+)(?:(\+)|,([0-9]+))?\}").match(shape, at)
    if found is None:
        raise ShapeError(shape, at, "a count such as {2}, {2,4} or {2+}",
                         '"' + shape[at:at + 8] + '"')
    lo = int(found.group(1))
    hi = None if found.group(2) else int(found.group(3)) if found.group(3) is not None else lo
    if hi is not None and (hi < lo or hi == 0):
        raise ShapeError(shape, at, "a count from n to m with m at least n and at least 1",
                         '"' + found.group(0) + '"')
    return lo, hi, found.end()


def _quoted_run(shape: str, at: int) -> tuple[str, int]:
    """Intent:
        The quoted text that opens at position `at` of `shape`, which holds a single quote, a
        doubled quote inside it read as one; and the position after its closing quote.

    Raises:
        ShapeError: the quote is never closed, or nothing stands between the quotes.
    """
    out = []
    here = at + 1
    while here < len(shape):
        if shape[here] != "'":
            out.append(shape[here])
            here += 1
        elif shape[here + 1:here + 2] == "'":
            out.append("'")
            here += 2
        else:
            if not out:
                raise ShapeError(shape, here, "at least one character between the quotes", '"\'"')
            return "".join(out), here + 1
    raise ShapeError(shape, here, f'"\'" to close the quoted text opened at position {at}',
                     "the end of the shape")


def _parse(shape: str, at: int, opened: int | None, symbols: frozenset[str],
           unknown: list[int]) -> tuple[tuple[_Item, ...], int]:
    """Intent:
        The items of `shape` from position `at` to the end, or, inside the bracket opened at
        position `opened`, to its closing bracket; and the position after them. A letter or
        digit not in `symbols` is read as that character and its position added to `unknown`.

    Raises:
        ShapeError: the shape does not read; the error names what was expected and where.
    """
    items: list[_Item] = []
    while at < len(shape):
        ch = shape[at]
        atom: Any
        if ch == "]":
            if opened is None:
                raise ShapeError(shape, at, 'a symbol, a character or "["',
                                 '"]" with no "[" open (write \\] for the character)')
            if not items:
                raise ShapeError(shape, at, 'at least one symbol or character inside the "["',
                                 '"]"')
            return tuple(items), at + 1
        if ch in "{}":
            raise ShapeError(shape, at, "a symbol, a character or a group before a count",
                             f'"{ch}" (write \\{ch} for the character)')
        if ch == "[":
            inner, after = _parse(shape, at + 1, at, symbols, unknown)
            atom, at = _Group(inner), after
        elif ch == "'":
            text, after = _quoted_run(shape, at)
            atom, at = _Run(text), after
        elif ch == "\\":
            if at + 1 >= len(shape):
                raise ShapeError(shape, at + 1, "a character after the backslash",
                                 "the end of the shape")
            atom, at = _Literal(shape[at + 1]), at + 2
        elif ch in symbols:
            atom, at = _Class(ch), at + 1
        else:
            if ch.isalnum():
                unknown.append(at)
            atom, at = _Literal(ch), at + 1
        optional = isinstance(atom, _Group)
        if at < len(shape) and shape[at] == "{":
            lo, hi, at = _count(shape, at)
            items.append(_Item(atom, lo, hi))
        else:
            items.append(_Item(atom, 0 if optional else 1, 1))
    if opened is not None:
        raise ShapeError(shape, at, f'"]" to close the "[" at position {opened}', "the end of the shape")
    return tuple(items), at


def _suffix(item: _Item, plain: tuple[int, int | None]) -> str:
    """Intent:
        The count of an item as canonical text writes it, empty when it is `plain`.
    """
    if (item.lo, item.hi) == plain:
        return ""
    return (f"{{{item.lo}+}}" if item.hi is None else f"{{{item.lo}}}" if item.lo == item.hi
            else f"{{{item.lo},{item.hi}}}")


def _bare(text: str) -> str:
    """Intent:
        Punctuation and spaces as a picture writes them outside quotes: each itself, with a
        backslash where it would otherwise open a bracket, a count, a quote or an escape.
    """
    return "".join(("\\" if c in _ESCAPED else "") + c for c in text)


def _text(items: tuple[_Item, ...]) -> str:
    """Intent:
        The canonical text of the items.

    Notes:
        Each atom is written as itself; a count that changes nothing is dropped and `{n,n}`
        is `{n}`. Quoted text holding no letter or digit is written bare, unless it is several
        characters under one count. A letter or digit written with a backslash is written as
        quoted text, joined with uncounted quoted text beside it; where it carries a count,
        or stands beside counted quoted text it cannot join, it keeps its backslash.
    """
    # each piece: its text, and for quoted text that may join its neighbours, that text
    pieces: list[tuple[str, str | None]] = []
    for item in items:
        atom = item.atom
        if isinstance(atom, _Group):
            pieces.append(("[" + _text(atom.items) + "]" + _suffix(item, (0, 1)), None))
            continue
        count = _suffix(item, (1, 1))
        if isinstance(atom, _Class):
            pieces.append((atom.symbol + count, None))
        elif isinstance(atom, _Literal):
            if atom.char.isalnum():
                pieces.append(("\\" + atom.char + count, None if count else atom.char))
            else:
                pieces.append((_bare(atom.char) + count, None))
        elif not any(c.isalnum() for c in atom.text) and (len(atom.text) == 1 or not count):
            pieces.append((_bare(atom.text) + count, None))
        elif count:
            pieces.append((_run_text(atom.text) + count, ""))
        else:
            pieces.append((_run_text(atom.text), atom.text))
    out: list[str] = []
    at = 0
    while at < len(pieces):
        if pieces[at][1] in (None, ""):
            out.append(pieces[at][0])
            at += 1
            continue
        end = at
        while end < len(pieces) and pieces[end][1] not in (None, ""):
            end += 1
        beside_counted = (at > 0 and pieces[at - 1][1] == "") or (end < len(pieces) and pieces[end][1] == "")
        escaped_only = all(p[0].startswith("\\") for p in pieces[at:end])
        if beside_counted and escaped_only:
            out += [p[0] for p in pieces[at:end]]
        else:
            out.append(_run_text("".join(str(p[1]) for p in pieces[at:end])))
        at = end
    return "".join(out)


# -- classes ---------------------------------------------------------------------

_ASCII_CLASSES: dict[str, tuple[tuple[int, int], ...]] = {
    "A": ((65, 90), (97, 122)), "a": ((97, 122),), "9": ((48, 57),), "X": ((0, 127),)}

#: the Unicode general categories of each symbol over `unicode`, by prefix
_CATEGORIES = {"A": "L", "a": "Ll", "9": "Nd"}


@functools.cache
def class_ranges(symbol: str, base: str) -> tuple[tuple[int, int], ...]:
    """Intent:
        The code points a built-in symbol stands for over the base language, as sorted,
        disjoint, inclusive ranges.

    Raises:
        ValueError: `symbol` is not one of `SYMBOLS` or `base` not one of `BASES`.
    """
    if symbol not in SYMBOLS or base not in BASES:
        raise ValueError(f"a class is one of {sorted(SYMBOLS)} over one of {BASES}, not "
                         f"{symbol!r} over {base!r}")
    if base == "ascii":
        return _ASCII_CLASSES[symbol]
    if symbol == "X":
        return ((0, sys.maxunicode),)
    prefix = _CATEGORIES[symbol]
    runs: list[list[int]] = []
    for code in range(sys.maxunicode + 1):
        if unicodedata.category(chr(code)).startswith(prefix):
            if runs and runs[-1][1] == code - 1:
                runs[-1][1] = code
            else:
                runs.append([code, code])
    return tuple((lo, hi) for lo, hi in runs)


#: per built-in symbol and base: the members at the edges of the class and, over `unicode`,
#: members outside ASCII
_PLAIN = {"A": "A", "a": "a", "9": "0", "X": "x"}
_EDGES = {
    ("A", "ascii"): "AZaz", ("a", "ascii"): "az", ("9", "ascii"): "09", ("X", "ascii"): "\x00\n ~\x7f",
    ("A", "unicode"): "AZazÉßΩ中ǅ", ("a", "unicode"): "azéßω",
    ("9", "unicode"): "09٣௧１", ("X", "unicode"): "\x00\n é\U0001f600",
}


@dataclass(frozen=True)
class _Classes:
    """What each symbol of one shape stands for: the alphabet it is
    bound to, else the built-in class over the base."""
    base: str
    bound: tuple[tuple[str, Alphabet], ...] = ()

    def of(self, symbol: str) -> Alphabet | None:
        """The alphabet `symbol` is bound to, or None for a built-in
        symbol left unbound."""
        return dict(self.bound).get(symbol)

    def ranges(self, symbol: str) -> tuple[tuple[int, int], ...]:
        """The code points the symbol stands for."""
        found = self.of(symbol)
        return found.ranges if found is not None else class_ranges(symbol, self.base)

    def has(self, symbol: str, ch: str) -> bool:
        """Whether the character is one the symbol stands for."""
        found = self.of(symbol)
        if found is not None:
            return found.has(ch)
        if self.base == "ascii":
            return any(lo <= ord(ch) <= hi for lo, hi in _ASCII_CLASSES[symbol])
        return symbol == "X" or unicodedata.category(ch).startswith(_CATEGORIES[symbol])

    def noun(self, symbol: str) -> str:
        """What the symbol stands for, in words."""
        found = self.of(symbol)
        return SYMBOLS[symbol] if found is None else f"a character of {found.text}"

    def plain(self, symbol: str) -> str:
        """The plainest character the symbol stands for."""
        found = self.of(symbol)
        return _PLAIN[symbol] if found is None else plain_character(found)

    def edges(self, symbol: str) -> str:
        """The characters at the edges of what the symbol stands
        for."""
        found = self.of(symbol)
        if found is None:
            return _EDGES[symbol, self.base]
        return "".join(dict.fromkeys(chr(c) for lo, hi in found.ranges[:4] for c in (lo, hi)))

    def wrong(self, symbol: str) -> str | None:
        """A character the symbol does not stand for, or None when it
        stands for every character."""
        found = self.of(symbol)
        candidates = "1aA- \x00é" + (outside_characters(found) if found is not None else "")
        return next((c for c in candidates if not self.has(symbol, c)), None)

    def pick(self, symbol: str, rng: random.Random | None) -> str:
        """One character the symbol stands for: the plainest without
        `rng`, else a random one, mostly from ASCII where the class has
        any."""
        if rng is None:
            return self.plain(symbol)
        found = self.of(symbol)
        if found is None and self.base == "unicode" and rng.random() < 0.3:
            return rng.choice(_EDGES[symbol, self.base])
        ranges = self.ranges(symbol) if found is not None else _ASCII_CLASSES[symbol]
        near = [(lo, min(hi, 127)) for lo, hi in ranges if lo <= 127]
        if found is not None and (not near or rng.random() < 0.2):
            near = list(ranges)
        lo, hi = rng.choice(near)
        return chr(rng.randint(lo, min(hi, lo + 4095)))


def _code(code: int) -> str:
    """Intent:
        One code point as it is written inside a character class of a regular expression: an
        ASCII letter or digit as itself, any other by its number.
    """
    if code < 128 and chr(code).isalnum():
        return chr(code)
    return f"\\x{code:02x}" if code < 256 else f"\\u{code:04x}" if code < 65536 else f"\\U{code:08x}"


def _class_pattern(ranges: tuple[tuple[int, int], ...]) -> str:
    """Intent:
        The character class of exactly the code points in `ranges`.
    """
    return "[" + "".join(_code(lo) if lo == hi else _code(lo) + "-" + _code(hi) for lo, hi in ranges) + "]"


# -- the four readings -----------------------------------------------------------

def _pattern(items: tuple[_Item, ...], classes: _Classes) -> str:
    """Intent:
        The Python regular expression that, read in full, admits what the items admit.
    """
    out = []
    for item in items:
        atom = item.atom
        lo, hi = item.lo, item.hi
        if isinstance(atom, _Group):
            piece = "(?:" + _pattern(atom.items, classes) + ")"
        elif isinstance(atom, _Class):
            piece = _class_pattern(classes.ranges(atom.symbol))
        elif isinstance(atom, _Run):
            piece = re.escape(atom.text)
            if len(atom.text) > 1 and (lo, hi) != (1, 1):
                piece = "(?:" + piece + ")"
        else:
            piece = re.escape(atom.char)
        out.append(piece + ("" if (lo, hi) == (1, 1) else "?" if (lo, hi) == (0, 1)
                            else f"{{{lo},}}" if hi is None else f"{{{lo}}}" if lo == hi
                            else f"{{{lo},{hi}}}"))
    return "".join(out)


def _expression(items: tuple[_Item, ...], classes: _Classes) -> tuple:
    """Intent:
        The regular expression of the items in the term module's own form.
    """
    parts = []
    for item in items:
        atom = item.atom
        if isinstance(atom, _Group):
            inner = _expression(atom.items, classes)
        elif isinstance(atom, _Class):
            inner = _regular._chars_re(classes.ranges(atom.symbol))
        else:
            text = atom.text if isinstance(atom, _Run) else atom.char
            inner = _regular._cat(*[_regular._chars_re(((ord(c), ord(c)),)) for c in text])
        parts.append(_regular._loop(inner, item.lo, item.hi))
    return _regular._cat(*parts)


def _ends(items: tuple[_Item, ...], classes: _Classes, text: str, starts: set[int]) -> set[int]:
    """Intent:
        The positions of `text` at which the items can end, having started at one of `starts`.
    """
    def once(item: _Item, at: set[int]) -> set[int]:
        atom = item.atom
        if isinstance(atom, _Group):
            return _ends(atom.items, classes, text, at)
        if isinstance(atom, _Class):
            return {p + 1 for p in at if p < len(text) and classes.has(atom.symbol, text[p])}
        literal = atom.text if isinstance(atom, _Run) else atom.char
        return {p + len(literal) for p in at if text.startswith(literal, p)}

    for item in items:
        now = starts
        for _ in range(item.lo):
            now = once(item, now)
        reached = set(now)
        taken = item.lo
        while now and (item.hi is None or taken < item.hi):
            now = once(item, now) - reached
            reached |= now
            taken += 1
        starts = reached
        if not starts:
            break
    return starts


# -- direct draws ----------------------------------------------------------------

@dataclass
class _Draw:
    """How one text is written from a shape. `rng` draws characters and
    counts (None: the plainest character, counts by `most`); `most`
    takes every count at its upper bound, else its lower (an unbounded
    count reads as two past its lower bound); `forced` fixes the count
    of chosen items; `swap`, a symbol and a character, writes that
    symbol as that character; `defect`, an item and a kind, is written
    into the text once, the first time that item is reached."""
    classes: _Classes
    rng: random.Random | None = None
    most: bool = False
    forced: dict[int, int] = field(default_factory=dict)
    swap: tuple[str, str] | None = None
    defect: tuple[int, str] | None = None

    def count(self, item: _Item) -> int:
        """The number of times `item` is taken in this draw."""
        top = item.hi if item.hi is not None else item.lo + 2
        if id(item) in self.forced:
            return self.forced[id(item)]
        if self.rng is not None:
            return self.rng.randint(item.lo, min(top, item.lo + 3))
        return top if self.most else item.lo

    def one(self, atom: Any, wrong: bool) -> str:
        """One taking of a class, a character or quoted text; with
        `wrong`, a character the class does not hold, or the text with
        its first character changed."""
        if isinstance(atom, _Class):
            if wrong:
                return self.classes.wrong(atom.symbol) or self.classes.plain(atom.symbol)
            if self.swap is not None and self.swap[0] == atom.symbol:
                return self.swap[1]
            return self.classes.pick(atom.symbol, self.rng)
        text = atom.text if isinstance(atom, _Run) else atom.char
        return (("y" if text[0] == "x" else "x") + text[1:]) if wrong else text

    def write(self, items: tuple[_Item, ...]) -> str:
        """The text of `items` under this draw."""
        out = []
        for item in items:
            kind = self.defect[1] if self.defect is not None and self.defect[0] == id(item) else None
            if kind is not None:
                self.defect = None
            n = self.count(item)
            if kind == "over" and item.hi is not None:
                n = item.hi + 1
            elif kind == "under":
                n = item.lo - 1
            elif kind in ("class", "half"):
                n = max(n, 1)
            for i in range(n):
                atom = item.atom
                if isinstance(atom, _Group):
                    piece = self.write(atom.items)
                    out.append(piece[:-1] if kind == "half" and i == 0 else piece)
                else:
                    out.append(self.one(atom, kind == "class" and i == 0))
        return "".join(out)


def _walk(items: tuple[_Item, ...], above: tuple[_Item, ...] = ()) -> Iterator[tuple[_Item, tuple[_Item, ...]]]:
    """Intent:
        Every item of the shape, outermost first, in the order written, each with the group
        items it lies inside.
    """
    for item in items:
        yield item, above
        if isinstance(item.atom, _Group):
            yield from _walk(item.atom.items, (*above, item))


def _defects(items: tuple[_Item, ...], classes: _Classes) -> list[tuple[_Item, tuple[_Item, ...], str, str]]:
    """Intent:
        Every single departure from the shape a near miss is written with: an item, the group
        items it lies inside, the kind of departure, and a note saying what it is.
    """
    out = []
    for item, above in _walk(items):
        atom = item.atom
        what = (classes.noun(atom.symbol) if isinstance(atom, _Class) else "an optional part"
                if isinstance(atom, _Group) else f"the text {_run_text(atom.text)}"
                if isinstance(atom, _Run) else f'the character "{atom.char}"')
        if isinstance(atom, _Class) and classes.wrong(atom.symbol) is not None:
            out.append((item, above, "class", f"a character of another class in place of {what}"))
        if isinstance(atom, (_Literal, _Run)):
            out.append((item, above, "class", f"another character in place of {what}"))
        if item.hi is not None:
            out.append((item, above, "over", f"{what} once more than its count allows"))
        if item.lo >= 1:
            out.append((item, above, "under", f"{what} once fewer than its count allows"))
        if isinstance(atom, _Group):
            out.append((item, above, "half", "an optional part cut one character short"))
    return out


class Shape:
    """A shape over a base language, `"ascii"` or `"unicode"`: the
    picture `text`, read once, with the alphabets its symbols are bound
    to. A binding is given by keyword (`W='alnum + "_"'`) or in
    `bindings`, a mapping from a symbol to an alphabet or the text of an
    alphabet expression, which also takes a digit as a symbol. Placed in
    `Annotated[str, Shape(...)]` it marks a record field. Shapes are
    equal when their picture, base and bindings are.

    Raises:
        UnknownSymbol: the picture holds a letter or digit that is neither a built-in symbol
            nor bound; the error offers both ways to mend it.
        ShapeError: the picture does not read, or a bound symbol is not in it; the error says
            what was expected and where.
        AlphabetError: a binding's text does not read as an alphabet expression.
        ValueError: the base is not one of `BASES`, a bound symbol is not one letter or digit,
            or a shape over `ascii` binds an alphabet that holds a character outside ASCII.
    """

    def __init__(self, text: str, base: str = "unicode", bindings: Mapping[str, Any] | None = None,
                 **symbols: Any) -> None:
        if base not in BASES:
            raise ValueError(f"a shape is over one of {BASES}, not {base!r}")
        if not isinstance(text, str) or text == "":
            raise ShapeError(str(text), 0, "at least one symbol or character", "the end of the shape")
        bound: dict[str, Alphabet] = {}
        for symbol, expression in {**dict(bindings or {}), **symbols}.items():
            if not isinstance(symbol, str) or len(symbol) != 1 or not symbol.isalnum():
                raise ValueError(f"a bound symbol is one letter or digit, not {symbol!r}")
            bound[symbol] = alphabet(expression)
            if base == "ascii" and bound[symbol].ranges[-1][1] > 127:
                raise ValueError(f"a shape over ascii binds ASCII alphabets, and {symbol} = "
                                 f"{bound[symbol].text} holds a character outside ASCII")
        self.text, self.base = text, base
        if base == "ascii":
            for at, ch in enumerate(text):
                if ord(ch) > 127:
                    raise ShapeError(text, at, "an ASCII character in a shape over ascii", f'"{ch}"')
        self.bindings: tuple[tuple[str, Alphabet], ...] = tuple(sorted(bound.items()))
        self._classes = _Classes(base, self.bindings)
        unknown: list[int] = []
        self._items, _ = _parse(text, 0, None, frozenset(SYMBOLS) | frozenset(bound), unknown)
        if unknown:
            groups: list[str] = []
            for i, at in enumerate(unknown):
                if i and at == unknown[i - 1] + 1:
                    groups[-1] += text[at]
                else:
                    groups.append(text[at])
            raise UnknownSymbol(text, unknown[0], tuple(dict.fromkeys(text[at] for at in unknown)),
                                tuple(dict.fromkeys(groups)), _text(self._items), self._bound_text())
        used = {item.atom.symbol for item, _ in _walk(self._items) if isinstance(item.atom, _Class)}
        for symbol in bound:
            if symbol not in used:
                raise ShapeError(text, len(text), f"the bound symbol {symbol} somewhere in the picture",
                                 f"no {symbol} (drop the binding, or use the symbol)")

    def _bound_text(self) -> str:
        """The bindings as they follow a picture: each `, S = alphabet`,
        sorted by symbol."""
        return "".join(f", {symbol} = {found.text}" for symbol, found in self.bindings)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Shape) and (self.text, self.base, self.bindings) == (
            other.text, other.base, other.bindings)

    def __hash__(self) -> int:
        return hash((self.text, self.base, self.bindings))

    def __repr__(self) -> str:
        bound = "".join(f", {symbol}={found.text!r}" for symbol, found in self.bindings
                        if symbol.isalpha())
        digits = {symbol: found.text for symbol, found in self.bindings if not symbol.isalpha()}
        return f"Shape({self.text!r}, {self.base!r}{', bindings=' + repr(digits) if digits else ''}{bound})"

    @property
    def shape(self) -> str:
        """The canonical text of the picture."""
        return _text(self._items)

    @property
    def arguments(self) -> str:
        """The shape as the arguments of the word, in canonical text:
        the quoted picture, then each binding, sorted by symbol."""
        return _quoted(self.shape) + self._bound_text()

    @property
    def pattern(self) -> str:
        """The Python regular expression that, read in full, admits
        exactly the shape's members: literals, character classes,
        `(?:...)` groups and counts only."""
        return _pattern(self._items, self._classes)

    def matches(self, text: object) -> bool:
        """Whether `text` is a member, by reading the picture against
        it one character at a time."""
        return isinstance(text, str) and len(text) in _ends(self._items, self._classes, text, {0})

    def term(self) -> dict[str, Any]:
        """The regular-language term of the shape's members, exact."""
        return {
            "kind": "regular_language", "version": _regular.TERM_VERSION,
            "alphabet": [[0, sys.maxunicode]], "exact": True,
            "language": _regular.to_node(_expression(self._items, self._classes)),
            "source": {"dialect": "shape", "shape": self.shape, "base": self.base,
                       "bindings": {symbol: found.text for symbol, found in self.bindings},
                       "unicode": unicodedata.unidata_version}}

    def explain(self) -> str:
        """The shape's members in plain words, a bound symbol's
        characters named by its alphabet."""
        from .explain import explain
        return explain(self.term(), names={found.ranges: found.text for _, found in self.bindings})

    def draw(self, rng: random.Random) -> str:
        """One member, written directly: each symbol a character of its
        class, each count a number it allows."""
        return _Draw(self._classes, rng).write(self._items)

    def members(self) -> tuple[str, ...]:
        """The members a probe must visit, written directly: every
        count at its lower bound and every count at its upper (two past
        the lower where there is none); each optional part and each
        count alone at its upper bound while the rest are at their
        lower; and each class at its edge characters, with the counts
        at their upper bounds and at their lower."""
        out = [_Draw(self._classes).write(self._items), _Draw(self._classes, most=True).write(self._items)]
        for item, _ in _walk(self._items):
            top = item.hi if item.hi is not None else item.lo + 2
            if top != item.lo:
                out.append(_Draw(self._classes, forced={id(item): top}).write(self._items))
        symbols = {i.atom.symbol for i, _ in _walk(self._items) if isinstance(i.atom, _Class)}
        for symbol in sorted(symbols):
            out += [_Draw(self._classes, most=most, swap=(symbol, edge)).write(self._items)
                    for most in (True, False) for edge in self._classes.edges(symbol)]
        return tuple(dict.fromkeys(out))

    def near_misses(self, rng: random.Random | None = None) -> tuple[tuple[str, str], ...]:
        """Texts one step outside the shape, each with a note: a
        position given a character of another class, a count taken once
        past its upper bound or once short of its lower, an optional
        part cut one character short, and a member with one character
        more, one fewer, a trailing newline or a space before it. Each
        is written from a member (the plainest, or one drawn with `rng`)
        and kept only when the shape does not admit it."""
        out: list[tuple[str, str]] = []
        for item, above, kind, note in _defects(self._items, self._classes):
            reached = {id(a): max(a.lo, 1) for a in above}
            draw = _Draw(self._classes, rng, forced=reached, defect=(id(item), kind))
            out.append((draw.write(self._items), note))
        for most in (False, True):
            member = _Draw(self._classes, rng, most=most).write(self._items)
            out += [(member + "\n", "a member with a trailing newline"),
                    (member + (member[-1:] or "a"), "a member with one character more"),
                    (member[:-1], "a member with one character fewer"),
                    (" " + member, "a member after a space")]
        seen: dict[str, str] = {}
        for text, note in out:
            if text not in seen and not self.matches(text):
                seen[text] = note
        return tuple(seen.items())

    def language(self) -> ShapeLanguage:
        """The text language of the shape's members."""
        return shape_language(self)

    def __get_pydantic_core_schema__(self, source: Any, handler: Any) -> Any:
        """The field's own validation, then this shape: a pydantic
        model refuses text the shape does not admit."""
        from pydantic_core import core_schema

        def check(value: Any) -> Any:
            if isinstance(value, str) and not self.matches(value):
                raise ValueError(f"text of the shape {self.arguments} over {self.base}")
            return value
        return core_schema.no_info_after_validator_function(check, handler(source))


@dataclass(frozen=True)
class ShapeLanguage(TextLanguage):
    """The members of a shape, as a text language. Draws are written
    from the shape directly; `outside` is a near miss."""
    shape: Shape | None = None
    pattern: str = ""

    def sample(self, rng: random.Random) -> str:
        assert self.shape is not None
        return self.shape.draw(rng)

    def outside(self, rng: random.Random) -> Any:
        assert self.shape is not None
        near = self.shape.near_misses(rng)
        return rng.choice(near)[0] if near else None

    def definition(self) -> dict[str, Any]:
        """The regular-language term of the shape's members, exact."""
        assert self.shape is not None
        return self.shape.term()

    def to_json(self) -> dict[str, Any]:
        assert self.shape is not None
        return {**super().to_json(), "shape": shape_json(self.shape), "definition": self.definition()}


def shape_json(shape: Shape) -> dict[str, Any]:
    """Intent:
        A shape as plain data: its base, its canonical picture, and its bindings, each symbol
        with the canonical text of its alphabet.
    """
    return {"base": shape.base, "shape": shape.shape,
            "bindings": {symbol: found.text for symbol, found in shape.bindings}}


def shape_language(shape: Shape | str, base: str = "unicode",
                   bindings: Mapping[str, Any] | None = None) -> ShapeLanguage:
    """The text language of a shape's members, over `ascii` or
    `unicode`: membership by the shape's own reading, draws written
    directly from it, hazards its boundary members, `outside` a near
    miss, and the exact term under `definition` in its persisted form.

    Raises:
        ShapeError: the shape does not read.
        ValueError: the base is not one of `BASES`, or a binding is not an alphabet.
    """
    found = shape if isinstance(shape, Shape) else Shape(shape, base, bindings)
    under = ASCII if found.base == "ascii" else UNICODE
    return ShapeLanguage(
        f"{found.base}, shape ({found.arguments})", level="regular", accepts=found.matches,
        generate=found.draw, pool=under.pool, simplest="a", shape=found,
        pattern=found.pattern,
        extra_hazards=tuple(HazardValue("text", m, "a member at a boundary of the shape")
                            for m in found.members()))


# -- the readings as functions of text ---------------------------------------------

def _reads(shape: str, base: str, text: str) -> bool:
    """Intent:
        Whether `text` is a member of the shape over the base, by the shape's own reading.

    Claims:
        any_text_is_any_number_of_any_character: for text in L[unicode], f("X{0+}", "unicode", text) == True
        digits_are_any_number_of_digits: for text in L[digit], f("9{0+}", "ascii", text) == True
        ascii_text_is_any_number_of_ascii_characters: for text in L[ascii], f("X{0+}", "ascii", text) == True
        ascii_letters_are_any_number_of_letters: for text in L[alpha], f("A{0+}", "ascii", text) == True
        a_drawn_postcode_is_a_member: for text in L[mathema_language.text.shape._POSTCODES], f("AA99[ ]9AA", "ascii", text) == True
        a_near_miss_of_a_postcode_is_not: for text in L[mathema_language.text.shape._NEAR_POSTCODES], f("AA99[ ]9AA", "ascii", text) == False
        a_postcode_is_also_seven_or_eight_of_anything: for text in L[mathema_language.text.shape._POSTCODES], f("X{7,8}", "ascii", text) == True
        a_postcode_is_a_member: f("AA99[ ]9AA", "ascii", "SW19 3AB") == True
        a_trailing_newline_is_not: f("AA99[ ]9AA", "ascii", "SW19 3AB\\n") == False

    Raises:
        ShapeError: the shape does not read.
        ValueError: the base is not one of `BASES`.
    """
    return _shape(shape, base).matches(text)


def _pattern_reads(shape: str, base: str, text: str) -> bool:
    """Intent:
        Whether `text` is a member of the shape over the base, by the shape's regular
        expression read in full.

    Claims:
        the_pattern_admits_every_drawn_member: for text in L[mathema_language.text.shape._POSTCODES], f("AA99[ ]9AA", "ascii", text) == True
        the_pattern_refuses_every_near_miss: for text in L[mathema_language.text.shape._NEAR_POSTCODES], f("AA99[ ]9AA", "ascii", text) == False
        the_pattern_admits_every_drawn_member_of_a_counted_shape: for text in L[mathema_language.text.shape._COUNTED], f("a{2,3}[ 9{1,2}]'b'", "ascii", text) == True
        the_pattern_refuses_every_near_miss_of_a_counted_shape: for text in L[mathema_language.text.shape._NEAR_COUNTED], f("a{2,3}[ 9{1,2}]'b'", "ascii", text) == False
        the_pattern_agrees_on_digits_either_side_of_a_count: let reads = mathema_language.text.shape._reads, for text in L[digit, len <= 6], f("9{2,4}", "unicode", text) == reads("9{2,4}", "unicode", text)
        the_pattern_agrees_on_any_text: let reads = mathema_language.text.shape._reads, for text in L[unicode], f("A{0+}9{0+}X{0,2}", "unicode", text) == reads("A{0+}9{0+}X{0,2}", "unicode", text)

    Raises:
        ShapeError: the shape does not read.
        ValueError: the base is not one of `BASES`.
    """
    return re.fullmatch(_shape(shape, base).pattern, text) is not None


def _term_reads(shape: str, base: str, text: str) -> bool:
    """Intent:
        Whether `text` is in the shape's regular-language term.

    Claims:
        the_term_admits_every_drawn_member: for text in L[mathema_language.text.shape._POSTCODES], f("AA99[ ]9AA", "ascii", text) == True
        the_term_refuses_every_near_miss: for text in L[mathema_language.text.shape._NEAR_POSTCODES], f("AA99[ ]9AA", "ascii", text) == False
        the_term_admits_every_drawn_member_of_a_counted_shape: for text in L[mathema_language.text.shape._COUNTED], f("a{2,3}[ 9{1,2}]'b'", "ascii", text) == True
        the_term_refuses_every_near_miss_of_a_counted_shape: for text in L[mathema_language.text.shape._NEAR_COUNTED], f("a{2,3}[ 9{1,2}]'b'", "ascii", text) == False
        the_term_agrees_on_digits_either_side_of_a_count: let reads = mathema_language.text.shape._reads, for text in L[digit, len <= 6], f("9{2,4}", "unicode", text) == reads("9{2,4}", "unicode", text)
        the_term_agrees_on_alphanumerics: let reads = mathema_language.text.shape._reads, for text in L[unicode_alnum], f("A{0+}9{0+}", "unicode", text) == reads("A{0+}9{0+}", "unicode", text)

    Raises:
        ShapeError: the shape does not read.
        ValueError: the base is not one of `BASES`.
    """
    return _regular.member(_shape(shape, base).term(), text)


def _canonical(shape: str) -> str:
    """Intent:
        The canonical text of a shape.

    Claims:
        a_canonical_shape_is_its_own_canonical_text: f(f("A{2,2}\\-[9]{0,1}9{1}\\K'-'")) == f("A{2,2}\\-[9]{0,1}9{1}\\K'-'")
        needless_marks_are_dropped: f("A{2,2}\\-[9]{0,1}9{1}\\K'-'") == "A{2}-[9]9'K'-"
        a_plain_shape_is_unchanged: f("AA99[ ]9AA") == "AA99[ ]9AA"

    Raises:
        ShapeError: the shape does not read.
    """
    return _shape(shape, "unicode").shape


@functools.lru_cache(maxsize=256)
def _shape(shape: str, base: str) -> Shape:
    """Intent:
        The shape read from its text over the base.

    Raises:
        ShapeError: the shape does not read.
        ValueError: the base is not one of `BASES`.
    """
    return Shape(shape, base)


def _near_language(shape: Shape) -> TextLanguage:
    """Intent:
        The text language of a shape's near misses: texts one step outside it, drawn from its
        own `near_misses`.
    """
    def draw(rng: random.Random) -> str:
        return rng.choice(shape.near_misses(rng))[0]

    return TextLanguage(f"near misses of shape ({shape.arguments})", level="predicate",
                        accepts=lambda text: not shape.matches(text), generate=draw)


#: languages the claims on this module quantify over, each named by its dotted path
_POSTCODES = shape_language("AA99[ ]9AA", "ascii")
_NEAR_POSTCODES = _near_language(Shape("AA99[ ]9AA", "ascii"))
_COUNTED = shape_language("a{2,3}[ 9{1,2}]'b'", "ascii")
_NEAR_COUNTED = _near_language(Shape("a{2,3}[ 9{1,2}]'b'", "ascii"))


# -- the word ----------------------------------------------------------------------

@dataclass(frozen=True)
class ShapeKind:
    """What `shape` means over one base language: the language's name,
    what the built-in symbols are there, and a complete example
    argument."""
    base: str
    classes: str
    example: tuple[str, ...]


#: the base languages `shape` has a meaning for, by name
SHAPE: dict[str, ShapeKind] = {kind.base: kind for kind in (
    ShapeKind("ascii", "A is A-Z or a-z, a is a-z, 9 is 0-9, X any ASCII character", ("AA99[ ]9AA",)),
    ShapeKind("unicode", "A is any Unicode letter, a any lower-case letter, 9 any decimal digit, "
                         "X any character", ("AA-9{4}",)),
)}


def claim_text(base: str, word: str, arguments: tuple[str, ...],
               bindings: Mapping[str, str] | None = None) -> str:
    """Intent:
        The complete domain text of `base` refined by a predicate word applied to quoted
        arguments and then bindings, sorted by symbol, as a claim writes it:
        `L[ascii, shape ("AW{0+}", W = alnum + "_")]`.
    """
    bound = "".join(f", {symbol} = {expression}" for symbol, expression in sorted((bindings or {}).items()))
    return f"L[{base}, {word} (" + ", ".join(_quoted(a) for a in arguments) + bound + ")]"


def shape_examples() -> dict[str, str]:
    """Intent:
        One complete example of the word for each base language it has a meaning for, by the
        language's name.
    """
    return {kind.base: claim_text(kind.base, "shape", kind.example) for kind in SHAPE.values()}


def shape_refusal(base: str, arguments: tuple[str, ...],
                  bindings: Mapping[str, str] | None = None) -> str | None:
    """Intent:
        Why `shape` with `arguments` and `bindings` is refused on the language named `base`,
        or None when it is not: the word has no meaning for that language, it takes one
        argument, or the picture or a binding does not read, with what was expected and
        where, and for an unknown letter or digit both ways to mend it.
    """
    if base not in SHAPE:
        return (f"'shape' has no meaning for L[{base}]: it pictures text in "
                + " or ".join(f"L[{name}]" for name in SHAPE))
    if len(arguments) != 1 or not isinstance(arguments[0], str):
        return (f"shape on L[{base}] takes one argument, the picture, not {len(arguments)}: "
                f"{claim_text(base, 'shape', SHAPE[base].example)}")
    try:
        Shape(arguments[0], base, bindings)
    except UnknownSymbol as e:
        return str(e)
    except ValueError as e:
        return f"shape ({_quoted(arguments[0])}) does not read on L[{base}]: {e}"
    return None


def _compiles(pattern: str) -> bool:
    """Intent:
        Whether `pattern` compiles as a Python regular expression.
    """
    try:
        re.compile(pattern)
    except (re.error, RecursionError, OverflowError):
        return False
    return True


def _mended(base: str, picture: str, bindings: Mapping[str, str] | None) -> tuple[str, dict[str, str]] | None:
    """Intent:
        The picture with its unknown letters and digits quoted as literal text, and the
        bindings in canonical text, when that is all that keeps the shape from reading on
        `base`; else None.
    """
    try:
        Shape(picture, base, bindings)
    except UnknownSymbol as e:
        try:
            mended = Shape(e.quoted, base, bindings)
        except ValueError:
            return None
        return mended.shape, {symbol: found.text for symbol, found in mended.bindings}
    except ValueError:
        return None
    return None


def suggest_shape(base: str, arguments: tuple[str, ...],
                  bindings: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """Intent:
        The complete domain texts a claim that wrote `shape` with `arguments` and `bindings`
        on the language named `base` most likely meant, best first, when that use is refused;
        empty when it is not refused.

    Notes:
        A picture refused only for letters or digits that are not symbols is suggested with
        them quoted as literal text, on the base given when it reads there, else on the
        others. A picture that reads on another base the word has a
        meaning for is suggested there, `ascii` first. One that does not read but compiles as
        a Python regular expression is suggested as `matches (re(r"...", python))`.
        Otherwise the base's own example is suggested, or `ascii`'s.
    """
    if shape_refusal(base, arguments, bindings) is None:
        return ()
    out: list[str] = []
    one = arguments[0] if len(arguments) == 1 and isinstance(arguments[0], str) else None
    if one is not None:
        for name in ([base, *(n for n in SHAPE if n != base)] if base in SHAPE else list(SHAPE)):
            mended = _mended(name, one, bindings)
            if mended is not None:
                out.append(claim_text(name, "shape", (mended[0],), mended[1]))
                if name == base:
                    break
        if not out:
            out += [claim_text(name, "shape", (one,), bindings) for name in SHAPE
                    if name != base and shape_refusal(name, (one,), bindings) is None]
        if not out and base in SHAPE and not bindings and _compiles(one):
            out.append(f'L[{base}, matches (re(r{_quoted(one)}, python))]')
    if not out:
        out.append(claim_text(base if base in SHAPE else "ascii", "shape",
                              SHAPE[base if base in SHAPE else "ascii"].example))
    return tuple(out)


__all__ = ["BASES", "SHAPE", "SYMBOLS", "Shape", "ShapeError", "ShapeKind", "ShapeLanguage",
           "UnknownSymbol", "claim_text", "class_ranges", "shape_examples", "shape_json",
           "shape_language", "shape_refusal", "suggest_shape"]
