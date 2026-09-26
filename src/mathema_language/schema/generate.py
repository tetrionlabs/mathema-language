# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Value generation per field of the neutral model, in-house: random
members by type under the field's constraints, the field's hazards
(the extremes, null where allowed, the text corpus in a string
field, the datetime64[ns] bounds and a DST edge, an empty list), the
simplest member shrinking heads for, and one non-member near the
boundary."""
from __future__ import annotations

import datetime as _dt
import decimal
import math
import random
from typing import Any

from .._surface import HazardValue
from ..text import UNICODE
from .checks import field_problems
from .model import NO_DEFAULT, Field, NeutralType

#: the closed range a nanosecond-resolution timestamp can hold
NS_MIN = _dt.datetime(1677, 9, 21, 0, 12, 43, 145225)
NS_MAX = _dt.datetime(2262, 4, 11, 23, 47, 16, 854775)
EPOCH = _dt.datetime(1970, 1, 1)
#: the last second before a spring-forward gap, a wall-clock time
#: that does not exist in zones that observe it
DST_EDGE = _dt.datetime(2026, 3, 29, 1, 59, 59)

_REJECTION_TRIES = 40


def _zone(t: NeutralType) -> _dt.tzinfo | None:
    if t.tz is None:
        return None
    if t.tz.upper() == "UTC":
        return _dt.UTC
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(t.tz)
    except Exception:
        return _dt.UTC


def _int_range(f: Field) -> tuple[int, int]:
    t, c = f.type, f.constraints
    lo, hi = -1_000_000, 1_000_000
    if t.bits:
        lo, hi = ((-(1 << (t.bits - 1)), (1 << (t.bits - 1)) - 1) if t.signed
                  else (0, (1 << t.bits) - 1))
    if c.min is not None:
        lo = max(lo, math.ceil(c.min))
    if c.exclusive_min is not None:
        lo = max(lo, math.floor(c.exclusive_min) + 1)
    if c.max is not None:
        hi = min(hi, math.floor(c.max))
    if c.exclusive_max is not None:
        hi = min(hi, math.ceil(c.exclusive_max) - 1)
    return lo, hi


def _float_range(f: Field) -> tuple[float, float]:
    c = f.constraints
    lo = float(c.low) if c.low is not None else -1e6
    hi = float(c.high) if c.high is not None else 1e6
    return lo, hi


def _length_range(f: Field, default_hi: int = 12) -> tuple[int, int]:
    c = f.constraints
    return (c.min_len or 0, c.max_len if c.max_len is not None else max(default_hi, c.min_len or 0))


def _draw_string(rng: random.Random, f: Field) -> str:
    lo, hi = _length_range(f)
    if f.constraints.regex is not None:
        from ..text.regex import draw_matching
        for _ in range(_REJECTION_TRIES):
            drawn = draw_matching(rng, f.constraints.regex)
            s = drawn if drawn is not None else UNICODE.sample(rng)
            if not field_problems(s, f):
                return s
        return ""
    n = rng.randint(lo, hi)
    s = UNICODE.sample(rng)
    while len(s) < n:
        s += UNICODE.sample(rng) or "a"
    return s[:n] if n else ""


def draw_raw(rng: random.Random, f: Field) -> Any:
    """One value of the field's type inside its bounds, before the
    opaque constraints (a regex, an enum) are applied by rejection."""
    t, c = f.type, f.constraints
    if c.const is not NO_DEFAULT:
        return c.const
    if c.enum is not None:
        return rng.choice(c.enum)
    base = t.base
    if base == "bool":
        return rng.random() < 0.5
    if base == "int":
        lo, hi = _int_range(f)
        if lo > hi:
            return lo
        return rng.choice((lo, hi, 0, 1)) if rng.random() < 0.15 and lo <= 0 <= hi else rng.randint(lo, hi)
    if base == "float":
        flo, fhi = _float_range(f)
        if f.nan_allowed and rng.random() < 0.05:
            return math.nan
        if rng.random() < 0.15:
            return rng.choice((flo, fhi, 0.0, -0.0, 0.5))
        return rng.uniform(flo, fhi)
    if base == "decimal":
        flo, fhi = _float_range(f)
        scale = t.scale if t.scale is not None else 2
        return decimal.Decimal(rng.uniform(flo, fhi)).quantize(decimal.Decimal(1).scaleb(-scale))
    if base == "string":
        return _draw_string(rng, f)
    if base == "binary":
        lo, hi = _length_range(f)
        return bytes(rng.randrange(256) for _ in range(rng.randint(lo, hi)))
    if base == "date":
        return (EPOCH + _dt.timedelta(days=rng.randint(-20000, 20000))).date()
    if base == "time":
        return _dt.time(rng.randrange(24), rng.randrange(60), rng.randrange(60))
    if base == "datetime":
        value = EPOCH + _dt.timedelta(seconds=rng.randint(-2_000_000_000, 4_000_000_000),
                                      microseconds=rng.randrange(1_000_000))
        return value.replace(tzinfo=_zone(t))
    if base == "duration":
        return _dt.timedelta(seconds=rng.randint(-10_000_000, 10_000_000))
    if base == "categorical":
        return rng.choice(t.levels) if t.levels else None
    if base == "list":
        lo, hi = _length_range(f, 4)
        item = t.item or NeutralType("any")
        return [draw(rng, Field("item", item)) for _ in range(rng.randint(lo, hi))]
    if base == "struct":
        return {sub.name: draw(rng, sub) for sub in (t.fields or ())}
    if base == "map":
        key_t = t.key or NeutralType("string")
        value_t = t.value or NeutralType("any")
        return {draw(rng, Field("key", key_t)): draw(rng, Field("value", value_t))
                for _ in range(rng.randint(0, 4))}
    return rng.choice((0, 1.5, "x", None, True))


def draw(rng: random.Random, f: Field) -> Any:
    """One member of the field: null one draw in eight where allowed,
    else a typed value the field's own checker accepts, found by
    rejection where the constraints are opaque."""
    if f.nullable and rng.random() < 0.125:
        return None
    value = draw_raw(rng, f)
    for _ in range(_REJECTION_TRIES):
        if not field_problems(value, f):
            return value
        value = draw_raw(rng, f)
    return value


def simplest(f: Field) -> Any:
    """The member shrinking substitutes first: the lowest bound or
    zero, the empty text, the first level, the epoch, an empty list;
    or null where the field allows it and nothing simpler is a
    member."""
    t, c = f.type, f.constraints
    candidates: list[Any] = []
    if c.const is not NO_DEFAULT:
        candidates.append(c.const)
    if c.enum:
        candidates.append(c.enum[0])
    base = t.base
    if base == "bool":
        candidates += [False]
    elif base == "int":
        lo, hi = _int_range(f)
        candidates += [0, lo, hi]
    elif base == "float":
        flo, fhi = _float_range(f)
        candidates += [0.0, flo, fhi]
    elif base == "decimal":
        candidates += [decimal.Decimal(0), decimal.Decimal(_float_range(f)[0])]
    elif base == "string":
        candidates += ["", "a" * (c.min_len or 0)]
    elif base == "binary":
        candidates += [b"", b"\x00" * (c.min_len or 0)]
    elif base == "date":
        candidates += [EPOCH.date()]
    elif base == "time":
        candidates += [_dt.time(0, 0)]
    elif base == "datetime":
        candidates += [EPOCH.replace(tzinfo=_zone(t))]
    elif base == "duration":
        candidates += [_dt.timedelta(0)]
    elif base == "categorical":
        candidates += list(t.levels or ())[:1]
    elif base == "list":
        candidates += [[]]
    elif base == "struct":
        candidates += [{sub.name: simplest(sub) for sub in (t.fields or ())}]
    elif base == "map":
        candidates += [{}]
    for candidate in candidates:
        if not field_problems(candidate, f):
            return candidate
    return None if f.nullable else candidates[0] if candidates else None


def hazards(f: Field) -> list[HazardValue]:
    """The members of the field a probe must visit, each tagged with
    its kind, in the order they are visited."""
    t, c = f.type, f.constraints
    out: list[tuple[str, Any, str]] = []
    if f.nullable:
        out.append(("null", None, "null"))
    base = t.base
    if base == "int":
        lo, hi = _int_range(f)
        out += [("extremity", lo, "the lowest member"), ("extremity", hi, "the highest member"),
                ("extremity", 0, "zero"), ("extremity", -1, "minus one"), ("extremity", 1, "one")]
    elif base == "float":
        flo, fhi = _float_range(f)
        out += [("extremity", flo, "the lowest member"), ("extremity", fhi, "the highest member"),
                ("extremity", 0.0, "zero"), ("extremity", -0.0, "negative zero"),
                ("extremity", 5e-324, "the smallest positive float"),
                ("extremity", 1e308, "near the largest float")]
        if f.nan_allowed:
            out.append(("null", math.nan, "NaN, a member of this field"))
    elif base == "decimal":
        out += [("extremity", decimal.Decimal(0), "zero")]
    elif base == "string":
        out.append(("empty", "", "the empty string"))
        for hazard in UNICODE.hazards():
            out.append((hazard.kind, hazard.value, hazard.note))
        if c.max_len is not None:
            out.append(("length", "a" * c.max_len, "the longest member"))
    elif base == "binary":
        out += [("empty", b"", "empty bytes"), ("control", b"\x00", "a NUL byte"),
                ("encoding", b"\xff\xfe", "bytes no UTF-8 decoder accepts")]
    elif base == "date":
        out += [("time", _dt.date(2024, 2, 29), "a leap day"), ("time", NS_MIN.date(), "the earliest ns date"),
                ("time", NS_MAX.date(), "the latest ns date")]
    elif base == "time":
        out += [("time", _dt.time(0, 0), "midnight"), ("time", _dt.time(23, 59, 59, 999999), "the last microsecond")]
    elif base == "datetime":
        zone = _zone(t)
        out += [("time", NS_MIN.replace(tzinfo=zone), "the earliest datetime64[ns]"),
                ("time", NS_MAX.replace(tzinfo=zone), "the latest datetime64[ns]"),
                ("time", DST_EDGE.replace(tzinfo=zone), "the second before a spring-forward gap"),
                ("time", EPOCH.replace(tzinfo=zone), "the epoch")]
    elif base == "duration":
        out += [("extremity", _dt.timedelta(0), "zero"), ("extremity", _dt.timedelta(days=-1), "negative")]
    elif base == "categorical":
        for level in t.levels or ():
            out.append(("shape", level, f"level {level!r}"))
    elif base == "list":
        out += [("shape", [], "an empty list")]
        if t.item is not None:
            out.append(("shape", [simplest(Field("item", t.item))], "one item"))
    elif base == "struct":
        out += [("shape", {sub.name: simplest(sub) for sub in (t.fields or ())}, "the simplest struct")]
    elif base == "map":
        out += [("shape", {}, "an empty map")]
    kept: list[HazardValue] = []
    seen: list[Any] = []
    for kind, value, note in out:
        if any(_same(value, s) for s in seen) or field_problems(value, f):
            continue
        seen.append(value)
        kept.append(HazardValue(kind, value, note))
    return kept


def _same(a: Any, b: Any) -> bool:
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    try:
        return bool(a == b) and type(a) is type(b)
    except Exception:
        return False


def outside(rng: random.Random, f: Field) -> tuple[Any, str] | None:
    """`(value, why)` for one non-member of the field near its
    boundary: null where none is allowed, past a bound, a wrong type,
    outside the enumeration, too long; or None when every value of
    the kind is a member."""
    t, c = f.type, f.constraints
    candidates: list[tuple[Any, str]] = []
    if not f.nullable:
        candidates.append((None, "null in a non-nullable field"))
    if c.enum is not None:
        candidates.append(("<outside>", "outside the enumeration"))
    if t.base in ("int", "float", "decimal"):
        if c.low is not None:
            candidates.append((c.low - 1, "below the lower bound"))
        if c.high is not None:
            candidates.append((c.high + 1, "above the upper bound"))
        if t.base == "int" and t.bits:
            lo, hi = _int_range(f)
            candidates.append((hi + 1, f"past the {t.render()} range"))
        candidates.append(("1", "a string where a number is expected"))
        if t.base == "float" and not f.nan_allowed:
            candidates.append((math.nan, "NaN in a field that excludes it"))
    elif t.base == "string":
        if c.max_len is not None:
            candidates.append(("a" * (c.max_len + 1), "one character too long"))
        if c.min_len:
            candidates.append(("a" * (c.min_len - 1), "one character too short"))
        candidates.append((0, "a number where text is expected"))
    elif t.base == "categorical":
        candidates.append(("<unused level>", "a level the categorical does not have"))
    elif t.base == "bool":
        candidates.append((2, "an int where a bool is expected"))
    elif t.base == "datetime":
        naive = EPOCH.replace(tzinfo=None) if t.tz else EPOCH.replace(tzinfo=_dt.UTC)
        candidates.append((naive, "naive where aware is expected" if t.tz else "aware where naive is expected"))
    elif t.base == "list":
        candidates.append(("not a list", "text where a list is expected"))
    elif t.base in ("date", "time", "duration", "binary", "struct", "map"):
        candidates.append((0, f"a number where a {t.base} is expected"))
    rng.shuffle(candidates)
    for value, why in candidates:
        if field_problems(value, f):
            return value, why
    return None


__all__ = ["DST_EDGE", "EPOCH", "NS_MAX", "NS_MIN", "draw", "draw_raw", "hazards",
           "outside", "simplest"]
