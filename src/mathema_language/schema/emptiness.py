# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Whether a field describes any value at all.

A field is empty when no value passes its own checker: a non-nullable
field whose constant or every enumerated value fails its type, a bound
range with nothing inside it, a length range whose minimum exceeds its
maximum, a regular expression that does not compile or has no match of
an allowed length, a categorical with no levels. `not_empty` decides it
by constructing candidate members from the field's own description
(its bounds and their neighbours, the first multiple of its divisor,
the shortest text of an allowed length, the shortest match of its
regular expression, its levels, an item for each required list entry)
and checking each with the field's checker; it never draws.

Two descriptions are not covered exactly: a regular expression with a
lookaround or a back reference, whose shortest match is not built, and
a non-integer divisor on a float, for which only the multiples nearest
the bounds are tried. For those, a field with members can read as
empty."""
from __future__ import annotations

import datetime as _dt
import decimal
import math
import re
import sys
from collections.abc import Iterator
from typing import Any

from .checks import field_problems
from .model import NO_DEFAULT, Field

if sys.version_info >= (3, 11):
    from re import _parser as sre_parse  # type: ignore[attr-defined]
else:
    import sre_parse

_EPOCH = _dt.datetime(1970, 1, 1)


def _number(x: Any) -> bool:
    """Intent:
        Whether `x` is an int, float or decimal, a bool not counting as one.
    """
    return isinstance(x, (int, float, decimal.Decimal)) and not isinstance(x, bool)


def _numeric_candidates(f: Field, integral: bool) -> Iterator[Any]:
    """Intent:
        Yields candidate numbers for a number field: 0, 1, -1, its bounds and their nearest inside
        neighbours, the midpoint, its bit width's extremes, and its divisor's multiples nearest the
        bounds.

    Notes:
        With `integral`, the neighbours are whole numbers; otherwise an exclusive bound's
        neighbour is the next double inside it.
    """
    c = f.constraints
    yield 0
    yield 1
    yield -1
    for bound in (c.min, c.max):
        if _number(bound):
            yield bound
            if integral:
                yield math.ceil(bound) if bound is c.min else math.floor(bound)
    for bound, step in ((c.exclusive_min, 1), (c.exclusive_max, -1)):
        if _number(bound):
            if integral:
                yield math.floor(bound) + 1 if step > 0 else math.ceil(bound) - 1
            else:
                yield math.nextafter(float(bound), math.inf * step)
    low, high = c.low, c.high
    if _number(low) and _number(high):
        yield (low + high) / 2 if not integral else (math.ceil(low) + math.floor(high)) // 2
    bits = f.type.bits
    if isinstance(bits, int) and 0 < bits <= 1024:
        yield -(1 << (bits - 1)) if f.type.signed else 0
        yield ((1 << (bits - 1)) - 1) if f.type.signed else (1 << bits) - 1
    m = c.multiple_of
    if _number(m) and m != 0:
        for bound in (low, high, 0):
            if _number(bound):
                k = math.ceil(bound / m) if bound is low else math.floor(bound / m)
                yield int(k * m) if integral and float(k * m).is_integer() else k * m


def _shortest_match(pattern: str) -> str | None:
    """Intent:
        Returns the shortest text the whole pattern matches, built from its parse, or None for a
        pattern that does not compile or holds a construct this does not build.
    """
    try:
        parsed = sre_parse.parse(pattern)
    except re.error:
        return None

    def build(items: Any) -> str | None:
        out = []
        for op, arg in items:
            name = str(op)
            if name == "LITERAL":
                out.append(chr(arg))
            elif name == "ANY":
                out.append("a")
            elif name == "IN":
                ch = _in_char(arg)
                if ch is None:
                    return None
                out.append(ch)
            elif name in ("MAX_REPEAT", "MIN_REPEAT", "POSSESSIVE_REPEAT"):
                lo, _hi, sub = arg
                piece = build(sub)
                if piece is None:
                    return None
                out.append(piece * lo)
            elif name == "SUBPATTERN":
                piece = build(arg[-1])
                if piece is None:
                    return None
                out.append(piece)
            elif name == "BRANCH":
                options = [o for o in (build(b) for b in arg[1]) if o is not None]
                if not options:
                    return None
                out.append(min(options, key=len))
            elif name in ("AT", "ATOMIC_GROUP"):
                if name == "ATOMIC_GROUP":
                    piece = build(arg)
                    if piece is None:
                        return None
                    out.append(piece)
            elif name == "CATEGORY":
                ch = {"CATEGORY_DIGIT": "0", "CATEGORY_WORD": "a", "CATEGORY_SPACE": " ",
                      "CATEGORY_NOT_DIGIT": "a", "CATEGORY_NOT_WORD": " ",
                      "CATEGORY_NOT_SPACE": "a"}.get(str(arg))
                if ch is None:
                    return None
                out.append(ch)
            else:
                return None
        return "".join(out)

    return build(parsed)


def _in_char(items: Any) -> str | None:
    """Intent:
        Returns one character a parsed character class admits, or None when none of the
        characters tried is admitted.
    """
    negate = any(str(op) == "NEGATE" for op, _ in items)
    if negate:
        excluded = set()
        for op, arg in items:
            if str(op) == "LITERAL":
                excluded.add(chr(arg))
        for ch in "aA0 _-xz9":
            if ch not in excluded and re.fullmatch(f"[{''.join(_class_text(items))}]", ch):
                return ch
        return None
    for op, arg in items:
        name = str(op)
        if name == "LITERAL":
            return chr(arg)
        if name == "RANGE":
            return chr(arg[0])
        if name == "CATEGORY":
            return {"CATEGORY_DIGIT": "0", "CATEGORY_WORD": "a", "CATEGORY_SPACE": " ",
                    "CATEGORY_NOT_DIGIT": "a", "CATEGORY_NOT_WORD": " ",
                    "CATEGORY_NOT_SPACE": "a"}.get(str(arg))
    return None


def _class_text(items: Any) -> Iterator[str]:
    """Intent:
        Yields a parsed character class's negation, literals and ranges back as regex text, for
        rebuilding the class between brackets.
    """
    for op, arg in items:
        name = str(op)
        if name == "NEGATE":
            yield "^"
        elif name == "LITERAL":
            yield re.escape(chr(arg))
        elif name == "RANGE":
            yield f"{re.escape(chr(arg[0]))}-{re.escape(chr(arg[1]))}"


def _text_candidates(f: Field) -> Iterator[str]:
    """Intent:
        Yields candidate texts for a string field: the empty text, the shortest text of its
        minimum length, and its pattern's shortest match, padded to that length when shorter.
    """
    c = f.constraints
    lo = c.min_len if isinstance(c.min_len, int) and c.min_len > 0 else 0
    yield ""
    yield "a" * lo
    if c.regex is not None:
        match = _shortest_match(c.regex)
        if match is not None:
            yield match
            if len(match) < lo and match:
                yield match + match[-1] * (lo - len(match))


def _candidates(f: Field, depth: int) -> Iterator[Any]:
    """Intent:
        Yields candidate members built from a field's description: null when nullable, its
        constant or enumeration when it has one, otherwise values of its type.

    Notes:
        A list or struct builds its items or fields from their own members, `depth` limiting how
        far nested types are followed.
    """
    c, t = f.constraints, f.type
    if f.nullable:
        yield None
    if c.const is not NO_DEFAULT:
        yield c.const
        return
    if c.enum is not None:
        yield from c.enum
        return
    base = t.base
    if base == "any":
        yield 0
    elif base == "bool":
        yield from (False, True)
    elif base == "int":
        yield from (int(v) for v in _numeric_candidates(f, integral=True)
                    if isinstance(v, int) or (isinstance(v, float) and v.is_integer()))
    elif base == "float":
        yield from (float(v) for v in _numeric_candidates(f, integral=False))
    elif base == "decimal":
        for v in _numeric_candidates(f, integral=False):
            try:
                d = decimal.Decimal(str(v))
                yield d if t.scale is None else d.quantize(decimal.Decimal(1).scaleb(-t.scale))
            except (decimal.InvalidOperation, ValueError):
                continue
    elif base == "string":
        yield from _text_candidates(f)
    elif base == "binary":
        lo = c.min_len if isinstance(c.min_len, int) and c.min_len > 0 else 0
        yield b"\x00" * lo
    elif base == "date":
        yield from (b for b in (c.min, c.max) if isinstance(b, _dt.date))
        yield _EPOCH.date()
    elif base == "time":
        yield _dt.time(0, 0)
    elif base == "datetime":
        yield from (b for b in (c.min, c.max) if isinstance(b, _dt.datetime))
        yield _EPOCH
        yield _EPOCH.replace(tzinfo=_dt.UTC)
    elif base == "duration":
        yield _dt.timedelta(0)
    elif base == "categorical":
        yield from (t.levels or ())
    elif base == "list":
        lo = c.min_len if isinstance(c.min_len, int) and c.min_len > 0 else 0
        if lo == 0:
            yield []
        elif t.item is not None and depth > 0:
            for item in _candidates(Field("item", t.item, nullable=t.nullable_items), depth - 1):
                yield [item] * lo
        elif t.item is None:
            yield [0] * lo
    elif base == "map":
        yield {}
    elif base == "struct" and depth > 0:
        values: dict[str, Any] = {}
        for sub in t.fields or ():
            found = _member(sub, depth - 1)
            if found is _NONE:
                return
            values[sub.name] = found
        try:
            yield t.construct(**values) if t.construct is not None else values
        except Exception:
            return


_NONE = object()


def _member(f: Field, depth: int) -> Any:
    """Intent:
        Returns the first candidate that passes the field's own checker, or the `_NONE` marker
        when none does.
    """
    for candidate in _candidates(f, depth):
        try:
            if not field_problems(candidate, f):
                return candidate
        except Exception:
            continue
    return _NONE


def not_empty(f: Field) -> bool:
    """Whether some value passes the field's own checker, decided by
    constructing candidate members from its description (see the module
    docstring for the two descriptions it does not cover exactly)."""
    return _member(f, depth=4) is not _NONE


__all__ = ["not_empty"]
