# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Shapes: text pictured one character at a time.

A shape is a picture of the text it admits, read left to right. Each
symbol stands for one character of one class:

- `A` a letter, `a` a lower-case letter, `9` a digit, `X` any one
  character;
- any other character is itself; a backslash makes the next character
  itself (`\\A` is the letter A, `\\[` a bracket, `\\\\` a backslash);
- `[ ... ]` is an optional part, and may hold optional parts;
- a count follows a symbol, a character or a bracket group: `{n}`
  exactly n, `{n,m}` from n to m, `{n+}` n or more. A counted group
  is no longer optional by itself: `[-99]{2}` is the part twice,
  `[-99]{0,2}` up to twice.

`AA99[ ]9AA` is two letters, two digits, an optional space, a digit and
two letters. The notation is a strict subset of regular expressions with
no alternation and no anchors, in which every position names its class,
so members and near misses are written down directly, never searched
for.

What a letter and a digit are follows the base language. Over `ascii`:
`A` is `A-Z` and `a-z`, `a` is `a-z`, `9` is `0-9`, `X` is any ASCII
character. Over `unicode`: `A` is any character of a Unicode letter
category (`L*`, what `str.isalpha` accepts of one character), `a` any
lower-case letter (category `Ll`), `9` any decimal digit (category
`Nd`, what `\\d` matches), `X` any character at all, a newline
included.

A shape states itself four ways that agree: `matches`, its own reading
of the picture; `pattern`, an equivalent Python regular expression to be
read in full, made of literals, character classes, `(?:...)` groups and
counts only; `term`, the regular-language term, always exact; and its
canonical text, the shape as written with three changes: a backslash
before a character that needs none is dropped, `{n,n}` is written
`{n}`, and a count that changes nothing (`{1}` after a symbol or
character, `{0,1}` after a group) is dropped.

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
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from .._surface import HazardValue
from . import _regular
from ._kit import TextLanguage
from .alphabets import ASCII, UNICODE

#: the characters that stand for a class
SYMBOLS = {"A": "a letter", "a": "a lower-case letter", "9": "a digit", "X": "any one character"}

#: the characters a shape writes with a backslash to mean themselves
_ESCAPED = "Aa9X[]{}\\"

#: the base languages a shape reads its classes from
BASES = ("ascii", "unicode")


class ShapeError(ValueError):
    """A shape that does not read, with what was expected and the
    position, counted from 0, where it was expected."""

    def __init__(self, shape: str, position: int, expected: str, found: str) -> None:
        self.shape, self.position, self.expected, self.found = shape, position, expected, found
        super().__init__(f"shape {shape!r}: expected {expected} at position {position}, found {found}")


@dataclass(frozen=True)
class _Class:
    """One character of the class a symbol names."""
    symbol: str


@dataclass(frozen=True)
class _Literal:
    """One given character."""
    char: str


@dataclass(frozen=True)
class _Group:
    """A bracketed part: its items in order."""
    items: tuple[Any, ...]


@dataclass(frozen=True)
class _Item:
    """An atom (a class, a character or a group) taken from `lo` to `hi`
    times, `hi` None for no upper bound. `counted` is whether a count
    was written."""
    atom: Any
    lo: int
    hi: int | None
    counted: bool = False


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


def _parse(shape: str, at: int, opened: int | None) -> tuple[tuple[_Item, ...], int]:
    """Intent:
        The items of `shape` from position `at` to the end, or, inside the bracket opened at
        position `opened`, to its closing bracket; and the position after them.

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
            inner, after = _parse(shape, at + 1, at)
            atom, at = _Group(inner), after
        elif ch == "\\":
            if at + 1 >= len(shape):
                raise ShapeError(shape, at + 1, "a character after the backslash",
                                 "the end of the shape")
            atom, at = _Literal(shape[at + 1]), at + 2
        else:
            atom, at = (_Class(ch) if ch in SYMBOLS else _Literal(ch)), at + 1
        optional = isinstance(atom, _Group)
        if at < len(shape) and shape[at] == "{":
            lo, hi, at = _count(shape, at)
            items.append(_Item(atom, lo, hi, counted=True))
        else:
            items.append(_Item(atom, 0 if optional else 1, 1))
    if opened is not None:
        raise ShapeError(shape, at, f'"]" to close the "[" at position {opened}', "the end of the shape")
    return tuple(items), at


def _text(items: tuple[_Item, ...]) -> str:
    """Intent:
        The canonical text of the items: each atom as written, a backslash only where one is
        needed, `{n,n}` as `{n}`, and no count where it changes nothing.
    """
    out = []
    for item in items:
        atom = item.atom
        if isinstance(atom, _Group):
            out.append("[" + _text(atom.items) + "]")
            plain = (0, 1)
        else:
            plain = (1, 1)
            out.append(atom.symbol if isinstance(atom, _Class)
                       else ("\\" if atom.char in _ESCAPED else "") + atom.char)
        if (item.lo, item.hi) != plain:
            out.append(f"{{{item.lo}+}}" if item.hi is None else f"{{{item.lo}}}" if item.lo == item.hi
                       else f"{{{item.lo},{item.hi}}}")
    return "".join(out)


# -- classes ---------------------------------------------------------------------

_ASCII_CLASSES: dict[str, tuple[tuple[int, int], ...]] = {
    "A": ((65, 90), (97, 122)), "a": ((97, 122),), "9": ((48, 57),), "X": ((0, 127),)}

#: the Unicode general categories of each symbol over `unicode`, by prefix
_CATEGORIES = {"A": "L", "a": "Ll", "9": "Nd"}


@functools.cache
def class_ranges(symbol: str, base: str) -> tuple[tuple[int, int], ...]:
    """Intent:
        The code points the symbol stands for over the base language, as sorted, disjoint,
        inclusive ranges.

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


def _in_class(symbol: str, base: str, ch: str) -> bool:
    """Intent:
        Whether the character `ch` is in the class the symbol stands for over the base.
    """
    if base == "ascii":
        return any(lo <= ord(ch) <= hi for lo, hi in _ASCII_CLASSES[symbol])
    return symbol == "X" or unicodedata.category(ch).startswith(_CATEGORIES[symbol])


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

def _pattern(items: tuple[_Item, ...], base: str) -> str:
    """Intent:
        The Python regular expression that, read in full, admits what the items admit.
    """
    out = []
    for item in items:
        atom = item.atom
        if isinstance(atom, _Group):
            piece = "(?:" + _pattern(atom.items, base) + ")"
        elif isinstance(atom, _Class):
            piece = _class_pattern(class_ranges(atom.symbol, base))
        else:
            piece = re.escape(atom.char)
        lo, hi = item.lo, item.hi
        out.append(piece + ("" if (lo, hi) == (1, 1) else "?" if (lo, hi) == (0, 1)
                            else f"{{{lo},}}" if hi is None else f"{{{lo}}}" if lo == hi
                            else f"{{{lo},{hi}}}"))
    return "".join(out)


def _expression(items: tuple[_Item, ...], base: str) -> tuple:
    """Intent:
        The regular expression of the items in the term module's own form.
    """
    parts = []
    for item in items:
        atom = item.atom
        if isinstance(atom, _Group):
            inner = _expression(atom.items, base)
        elif isinstance(atom, _Class):
            inner = _regular._chars_re(class_ranges(atom.symbol, base))
        else:
            inner = _regular._chars_re(((ord(atom.char), ord(atom.char)),))
        parts.append(_regular._loop(inner, item.lo, item.hi))
    return _regular._cat(*parts)


def _ends(items: tuple[_Item, ...], base: str, text: str, starts: set[int]) -> set[int]:
    """Intent:
        The positions of `text` at which the items can end, having started at one of `starts`.
    """
    def once(item: _Item, at: set[int]) -> set[int]:
        atom = item.atom
        if isinstance(atom, _Group):
            return _ends(atom.items, base, text, at)
        if isinstance(atom, _Class):
            return {p + 1 for p in at if p < len(text) and _in_class(atom.symbol, base, text[p])}
        return {p + 1 for p in at if p < len(text) and text[p] == atom.char}

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

#: per symbol and base: the plainest member, the members at the edges of the class, and, over
#: `unicode`, members outside ASCII
_PLAIN = {"A": "A", "a": "a", "9": "0", "X": "x"}
_EDGES = {
    ("A", "ascii"): "AZaz", ("a", "ascii"): "az", ("9", "ascii"): "09", ("X", "ascii"): "\x00\n ~\x7f",
    ("A", "unicode"): "AZazÉßΩ中ǅ", ("a", "unicode"): "azéßω",
    ("9", "unicode"): "09٣௧１", ("X", "unicode"): "\x00\n é\U0001f600",
}
#: per symbol: a character of another class, for a near miss
_WRONG = {"A": "1", "a": "A", "9": "a"}


def _pick(symbol: str, base: str, rng: random.Random | None) -> str:
    """Intent:
        One character of the symbol's class over the base: the plainest without `rng`, else a
        random one, from all of the class over `ascii` and from ASCII or the notable
        characters outside it over `unicode`.
    """
    if rng is None:
        return _PLAIN[symbol]
    if base == "unicode" and rng.random() < 0.3:
        return rng.choice(_EDGES[symbol, base])
    lo, hi = rng.choice(_ASCII_CLASSES[symbol])
    return chr(rng.randint(lo, hi))


@dataclass
class _Draw:
    """How one text is written from a shape. `rng` draws characters and
    counts (None: the plainest character, counts by `most`); `most`
    takes every count at its upper bound, else its lower (an unbounded
    count reads as two past its lower bound); `forced` fixes the count
    of chosen items; `defect`, an item and a kind, is written into the
    text once, the first time that item is reached."""
    base: str
    rng: random.Random | None = None
    most: bool = False
    forced: dict[int, int] = field(default_factory=dict)
    defect: tuple[int, str] | None = None

    def count(self, item: _Item) -> int:
        """The number of times `item` is taken in this draw."""
        top = item.hi if item.hi is not None else item.lo + 2
        if id(item) in self.forced:
            return self.forced[id(item)]
        if self.rng is not None:
            return self.rng.randint(item.lo, min(top, item.lo + 3))
        return top if self.most else item.lo

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
                elif kind == "class" and i == 0:
                    out.append(_WRONG[atom.symbol] if isinstance(atom, _Class)
                               else ("y" if atom.char == "x" else "x"))
                else:
                    out.append(_pick(atom.symbol, self.base, self.rng) if isinstance(atom, _Class)
                               else atom.char)
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


def _defects(items: tuple[_Item, ...]) -> list[tuple[_Item, tuple[_Item, ...], str, str]]:
    """Intent:
        Every single departure from the shape a near miss is written with: an item, the group
        items it lies inside, the kind of departure, and a note saying what it is.
    """
    out = []
    for item, above in _walk(items):
        atom = item.atom
        what = (SYMBOLS[atom.symbol] if isinstance(atom, _Class) else "an optional part"
                if isinstance(atom, _Group) else f'the character "{atom.char}"')
        if isinstance(atom, _Class) and atom.symbol in _WRONG:
            out.append((item, above, "class", f"a character of another class in place of {what}"))
        if isinstance(atom, _Literal):
            out.append((item, above, "class", f"another character in place of {what}"))
        if item.hi is not None:
            out.append((item, above, "over", f"{what} once more than its count allows"))
        if item.lo >= 1:
            out.append((item, above, "under", f"{what} once fewer than its count allows"))
        if isinstance(atom, _Group):
            out.append((item, above, "half", "an optional part cut one character short"))
    return out


@dataclass(frozen=True)
class Shape:
    """A shape over a base language, `"ascii"` or `"unicode"`: the
    picture `text`, read once and held in canonical form as `shape`.
    Placed in `Annotated[str, Shape(...)]` it marks a record field.

    Raises:
        ShapeError: the picture does not read; the error says what was expected and where.
        ValueError: the base is not one of `BASES`, or the shape over `ascii` holds a
            character outside ASCII.
    """
    text: str
    base: str = "unicode"
    _items: tuple[_Item, ...] = field(init=False, repr=False, compare=False, default=())

    def __post_init__(self) -> None:
        if self.base not in BASES:
            raise ValueError(f"a shape is over one of {BASES}, not {self.base!r}")
        if not isinstance(self.text, str) or self.text == "":
            raise ShapeError(str(self.text), 0, "at least one symbol or character",
                             "the end of the shape")
        items, _ = _parse(self.text, 0, None)
        if self.base == "ascii":
            for at, ch in enumerate(self.text):
                if ord(ch) > 127:
                    raise ShapeError(self.text, at, "an ASCII character in a shape over ascii",
                                     f'"{ch}"')
        object.__setattr__(self, "_items", items)

    @property
    def shape(self) -> str:
        """The canonical text of the shape."""
        return _text(self._items)

    @property
    def pattern(self) -> str:
        """The Python regular expression that, read in full, admits
        exactly the shape's members: literals, character classes,
        `(?:...)` groups and counts only."""
        return _pattern(self._items, self.base)

    def matches(self, text: object) -> bool:
        """Whether `text` is a member, by reading the picture against
        it one character at a time."""
        return isinstance(text, str) and len(text) in _ends(self._items, self.base, text, {0})

    def term(self) -> dict[str, Any]:
        """The regular-language term of the shape's members, exact."""
        return {
            "kind": "regular_language", "version": _regular.TERM_VERSION,
            "alphabet": [[0, sys.maxunicode]], "exact": True,
            "language": _regular.to_node(_expression(self._items, self.base)),
            "source": {"dialect": "shape", "shape": self.shape, "base": self.base,
                       "unicode": unicodedata.unidata_version}}

    def draw(self, rng: random.Random) -> str:
        """One member, written directly: each symbol a character of its
        class, each count a number it allows."""
        return _Draw(self.base, rng).write(self._items)

    def members(self) -> tuple[str, ...]:
        """The members a probe must visit, written directly: every
        count at its lower bound and every count at its upper (two past
        the lower where there is none); each optional part and each
        count alone at its upper bound while the rest are at their
        lower; and each class at its edge characters."""
        out = [_Draw(self.base).write(self._items), _Draw(self.base, most=True).write(self._items)]
        for item, _ in _walk(self._items):
            top = item.hi if item.hi is not None else item.lo + 2
            if top != item.lo:
                out.append(_Draw(self.base, forced={id(item): top}).write(self._items))
        symbols = {i.atom.symbol for i, _ in _walk(self._items) if isinstance(i.atom, _Class)}
        for symbol in sorted(symbols):
            out += [_swap(self._items, self.base, symbol, edge, most)
                    for most in (True, False) for edge in _EDGES[symbol, self.base]]
        return tuple(dict.fromkeys(out))

    def near_misses(self, rng: random.Random | None = None) -> tuple[tuple[str, str], ...]:
        """Texts one step outside the shape, each with a note: a
        position given a character of another class, a count taken once
        past its upper bound or once short of its lower, an optional
        part cut one character short, and a member with one character
        more, one fewer, or a trailing newline. Each is written from a
        member (the plainest, or one drawn with `rng`) and kept only
        when the shape does not admit it."""
        out: list[tuple[str, str]] = []
        for item, above, kind, note in _defects(self._items):
            reached = {id(a): max(a.lo, 1) for a in above}
            draw = _Draw(self.base, rng, forced=reached, defect=(id(item), kind))
            out.append((draw.write(self._items), note))
        for most in (False, True):
            member = _Draw(self.base, rng, most=most).write(self._items)
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
                raise ValueError(f"text of the shape {self.shape!r} over {self.base}")
            return value
        return core_schema.no_info_after_validator_function(check, handler(source))


def _swap(items: tuple[_Item, ...], base: str, symbol: str, ch: str, most: bool) -> str:
    """Intent:
        The member with every count at its upper bound (`most`) or its lower, and every
        `symbol` written as `ch`.
    """
    out = []
    for item in items:
        atom = item.atom
        n = item.lo if not most else item.hi if item.hi is not None else item.lo + 2
        for _ in range(n):
            if isinstance(atom, _Group):
                out.append(_swap(atom.items, base, symbol, ch, most))
            elif isinstance(atom, _Class):
                out.append(ch if atom.symbol == symbol else _PLAIN[atom.symbol])
            else:
                out.append(atom.char)
    return "".join(out)


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
        return {**super().to_json(), "shape": {"base": self.shape.base, "shape": self.shape.shape},
                "definition": self.definition()}


def _quoted(text: str) -> str:
    """Intent:
        `text` between double quotes, as an argument is written inside a predicate's brackets:
        a backslash and a double quote each take a backslash before them.
    """
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def shape_language(shape: Shape | str, base: str = "unicode") -> ShapeLanguage:
    """The text language of a shape's members, over `ascii` or
    `unicode`: membership by the shape's own reading, draws written
    directly from it, hazards its boundary members, `outside` a near
    miss, and the exact term under `definition` in its persisted form.

    Raises:
        ShapeError: the shape does not read.
        ValueError: the base is not one of `BASES`.
    """
    found = shape if isinstance(shape, Shape) else Shape(shape, base)
    under = ASCII if found.base == "ascii" else UNICODE
    return ShapeLanguage(
        f"{found.base}, shape ({_quoted(found.shape)})", level="regular", accepts=found.matches,
        generate=found.draw, pool=under.pool, simplest=_PLAIN["a"], shape=found,
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
        answers_any_text: for text in L[unicode], f("AA99[ ]9AA", "ascii", text) in {True, False}
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
        the_pattern_agrees_on_ascii_text: let reads = mathema_language.text.shape._reads, for text in L[ascii], f("a{2,3}[ 9{1,2}]b", "ascii", text) == reads("a{2,3}[ 9{1,2}]b", "ascii", text)
        the_pattern_agrees_on_any_text: let reads = mathema_language.text.shape._reads, for text in L[unicode], f("A{0+}9{0+}X{0,2}", "unicode", text) == reads("A{0+}9{0+}X{0,2}", "unicode", text)
        the_pattern_agrees_on_digits: let reads = mathema_language.text.shape._reads, for text in L[digit], f("9{2,4}", "unicode", text) == reads("9{2,4}", "unicode", text)

    Raises:
        ShapeError: the shape does not read.
        ValueError: the base is not one of `BASES`.
    """
    return re.fullmatch(_shape(shape, base).pattern, text) is not None


def _term_reads(shape: str, base: str, text: str) -> bool:
    """Intent:
        Whether `text` is in the shape's regular-language term.

    Claims:
        the_term_agrees_on_ascii_text: let reads = mathema_language.text.shape._reads, for text in L[ascii], f("a{2,3}[ 9{1,2}]b", "ascii", text) == reads("a{2,3}[ 9{1,2}]b", "ascii", text)
        the_term_agrees_on_any_text: let reads = mathema_language.text.shape._reads, for text in L[unicode], f("A{0+}9{0+}X{0,2}", "unicode", text) == reads("A{0+}9{0+}X{0,2}", "unicode", text)
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
        a_canonical_shape_is_its_own_canonical_text: f(f("A{2,2}\\-[9]{0,1}9{1}")) == f("A{2,2}\\-[9]{0,1}9{1}")
        needless_marks_are_dropped: f("A{2,2}\\-[9]{0,1}9{1}") == "A{2}-[9]9"
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


# -- the word ----------------------------------------------------------------------

@dataclass(frozen=True)
class ShapeKind:
    """What `shape` means over one base language: the language's name,
    what a letter and a digit are there, and a complete example
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


def claim_text(base: str, word: str, arguments: tuple[str, ...]) -> str:
    """Intent:
        The complete domain text of `base` refined by a predicate word applied to quoted
        arguments, as a claim writes it: `L[ascii, shape ("AA99")]`.
    """
    return f"L[{base}, {word} (" + ", ".join(_quoted(a) for a in arguments) + ")]"


def shape_examples() -> dict[str, str]:
    """Intent:
        One complete example of the word for each base language it has a meaning for, by the
        language's name.
    """
    return {kind.base: claim_text(kind.base, "shape", kind.example) for kind in SHAPE.values()}


def shape_refusal(base: str, arguments: tuple[str, ...]) -> str | None:
    """Intent:
        Why `shape` with `arguments` is refused on the language named `base`, or None when it
        is not: the word has no meaning for that language, it takes one argument, or the
        argument does not read as a shape, with what was expected and where.
    """
    if base not in SHAPE:
        return (f"'shape' has no meaning for L[{base}]: it pictures text in "
                + " or ".join(f"L[{name}]" for name in SHAPE))
    if len(arguments) != 1 or not isinstance(arguments[0], str):
        return (f"shape on L[{base}] takes one argument, the picture, not {len(arguments)}: "
                f"{claim_text(base, 'shape', SHAPE[base].example)}")
    try:
        Shape(arguments[0], base)
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


def suggest_shape(base: str, arguments: tuple[str, ...]) -> tuple[str, ...]:
    """Intent:
        The complete domain texts a claim that wrote `shape` with `arguments` on the language
        named `base` most likely meant, best first, when that use is refused; empty when it is
        not refused.

    Notes:
        A picture that reads is suggested over each base the word has a meaning for, `ascii`
        first. One that does not read but compiles as a Python regular expression is
        suggested as `matches (re(r"...", python))` on the base given, or on `unicode` when
        the base is not text the word knows. Otherwise the base's own example is suggested,
        or `ascii`'s.
    """
    if shape_refusal(base, arguments) is None:
        return ()
    out: list[str] = []
    one = arguments[0] if len(arguments) == 1 and isinstance(arguments[0], str) else None
    if one is not None:
        out += [claim_text(name, "shape", (one,)) for name in SHAPE
                if name != base and shape_refusal(name, (one,)) is None]
        if not out and base in SHAPE and _compiles(one):
            out.append(f'L[{base}, matches (re(r{_quoted(one)}, python))]')
    if not out:
        out.append(claim_text(base if base in SHAPE else "ascii", "shape",
                              SHAPE[base if base in SHAPE else "ascii"].example))
    return tuple(out)


__all__ = ["BASES", "SHAPE", "SYMBOLS", "Shape", "ShapeError", "ShapeKind", "ShapeLanguage",
           "claim_text", "class_ranges", "shape_examples", "shape_language", "shape_refusal",
           "suggest_shape"]
