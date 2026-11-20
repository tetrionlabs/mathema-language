# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""`within`: a text language bounded to a region, the region's meaning
set by the base language.

- `L[path]`: a subtree. `path_within` (in `path_language`).
- `L[ipv4]`, `L[ipv6]`: a CIDR block, named by its network address
  (`10.0.0.0/8`, `2001:db8::/32`). A member is any spelling
  `ipaddress` reads of an address in the block.
- `L[iso_date]`: a closed interval of dates, two bounds. A member is any
  spelling `date.fromisoformat` reads, on the running Python, of a date
  from the first bound to the last.
- `L[iso_datetime]`: a closed interval, two bounds of one awareness.
  Between naive bounds a member is a naive datetime from the first to the
  last; between aware bounds it is an aware datetime whose instant lies
  from the first to the last, written at any offset. A datetime of the
  other awareness is never a member.
- `L[url]`: an origin, or a path prefix under one. A region is a URL with
  no user part, query or fragment. A member has the region's scheme and
  host (read in lower case) and port (the scheme's own when none is
  written: 80 for http, 443 for https), and no user part. When the region
  names a path other than `/`, the member's path is that path or
  continues it after a `/`, holds no backslash, and has no `..` segment,
  plain or percent-encoded (`%2e`).

Several regions are their union. Membership is the standard library's
reading (`ipaddress`, `datetime`, `urllib.parse`); beside it each
language but the datetimes states `pattern`, a regular expression that,
read in full, admits exactly the members, and every language carries a
regular-language term of it under `definition` in its persisted form.
The datetime interval's term is a pair of bounds: `at_most` holds the
members written as `datetime.isoformat` writes them, at the offset of
the first bound; `at_least` holds any text that starts with a date, in
any spelling, from the day before the first bound to the day after the
last.

Draws are members; hazards are the members at the boundary (the first
and last address of a block, the bounds of an interval, the region's own
URL) in their other spellings; `outside` draws a value just past it (the
address before or after the block, the day before or after the interval,
a URL with a user part, another port, or a host that only starts with
the region's).

`WITHIN` is the word's own description, for a registry: the base
languages it has a meaning for, an example for each, the form its
arguments take, and `suggest_within`, which guesses the base a claim
meant from the arguments it gave.
"""
from __future__ import annotations

import datetime as _dt
import functools
import ipaddress
import random
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .._surface import HazardValue
from . import _regular
from ._finite import finite_complement, finite_pattern
from ._kit import TextLanguage
from .path_language import PATH, _normal_root, _quoted, path_within
from .predicates import IPV4, IPV6, ISO_DATE, ISO_DATETIME
from .url_language import URL, url_parts

_HEXTET = "[0-9A-Fa-f]{1,4}"


@dataclass(frozen=True)
class WithinLanguage(TextLanguage):
    """A base text language bounded to `regions`, written as the word's
    arguments. `pattern`, when stated, is the regular expression that,
    read in full, admits exactly the members; `bounds`, in its place, is
    a pair of expressions: the first admits every member, the second
    only members. `near` are values just past the boundary."""
    base: Any = None
    regions: tuple[str, ...] = ()
    pattern: str | None = None
    bounds: tuple[str, str] | None = None
    near: tuple[HazardValue, ...] = ()

    def outside(self, rng: random.Random) -> Any:
        near = [h.value for h in self.near if not self.contains(h.value)]
        if near:
            return rng.choice(near)
        return None if self.base is None else self.base.outside(rng)

    def definition(self) -> dict[str, Any]:
        """The regular-language term of this language: exact where it
        states a pattern, else a pair of bounds, `at_least` holding
        every member and `at_most` only members."""
        return _definition(self.pattern, self.bounds)

    def to_json(self) -> dict[str, Any]:
        base = getattr(self.base, "name", None)
        return {**super().to_json(), "within": {"base": base, "regions": list(self.regions)},
                "definition": self.definition()}


@functools.lru_cache(maxsize=256)
def _definition(pattern: str | None, bounds: tuple[str, str] | None) -> dict[str, Any]:
    """Intent:
        The regular-language term of a pattern read in full, or, for a pair of patterns, the
        term whose `at_least` is the first and whose `at_most` is the second.

    Raises:
        ValueError: neither a pattern nor a pair is given.
    """
    if pattern is not None:
        return _regular.term(pattern, re.DOTALL, "matches")
    if bounds is None:
        raise ValueError("a definition is of a pattern or of a pair of bounds")
    least, most = (_regular.term(p, re.DOTALL, "matches") for p in bounds)
    doc = {key: value for key, value in least.items() if key not in ("language", "source")}
    doc.update(exact=False, at_least=least["language"], at_most=most["language"])
    doc["source"] = {**least["source"], "pattern": bounds[0], "at_most_pattern": bounds[1],
                     "not_exact": ["an interval of datetimes"]}
    return doc


def _name(base: Any, regions: tuple[str, ...]) -> str:
    """Intent:
        The text inside `L[...]` for `base` within `regions`: the base's name, then the word
        and its quoted arguments in brackets.
    """
    return f"{base.name}, within (" + ", ".join(_quoted(r) for r in regions) + ")"


def _build(base: Any, regions: tuple[str, ...], accepts: Callable[[str], bool],
           generate: Callable[[random.Random], str], members: list[tuple[str, str]],
           near: list[tuple[str, str]], kind: str, pattern: str | None = None,
           bounds: tuple[str, str] | None = None) -> WithinLanguage:
    """Intent:
        The language of `base` within `regions`: membership by `accepts`, draws by `generate`,
        `members` (text, note) offered as hazards where they are members, `near` as outside
        values where they are not.
    """
    def hazards(pairs: list[tuple[str, str]], keep: bool) -> tuple[HazardValue, ...]:
        seen: dict[str, HazardValue] = {}
        for text, note in pairs:
            if text not in seen and accepts(text) == keep:
                seen[text] = HazardValue(kind, text, note)
        return tuple(seen.values())

    return WithinLanguage(
        _name(base, regions), level="regular" if pattern is not None else "predicate",
        accepts=accepts, generate=generate, pool=base.pool, outside_pool=base.outside_pool,
        simplest=base.simplest, base=base, regions=regions, pattern=pattern, bounds=bounds,
        extra_hazards=(*hazards(members, True), *base.extra_hazards), near=hazards(near, False))


# -- IP addresses: CIDR blocks ---------------------------------------------------

def _octet(lo: int, hi: int) -> str:
    """Intent:
        The expression of the decimal numbers from `lo` to `hi`, written without leading zeros.
    """
    return finite_pattern(str(i) for i in range(lo, hi + 1))


@functools.lru_cache(maxsize=256)
def _hextet(lo: int, hi: int) -> str:
    """Intent:
        The expression of one IPv6 group whose value is from `lo` to `hi`: one to four
        hexadecimal digits in either case, leading zeros allowed.
    """
    if (lo, hi) == (0, 0xFFFF):
        return _HEXTET
    words = {format(v, f"0{width}x") for width in range(1, 5)
             for v in range(lo, min(hi, 16 ** width - 1) + 1)}
    return finite_pattern(words, fold=True)


def _ipv4_tail(first: int, last: int) -> str:
    """Intent:
        The expression of the dotted-decimal addresses whose four octets each lie between the
        matching octets of `first` and `last`.
    """
    return r"\.".join(_octet((first >> s) & 255, (last >> s) & 255) for s in (24, 16, 8, 0))


def _ipv4_block(block: ipaddress.IPv4Network) -> str:
    """Intent:
        The expression of every text `ipaddress.IPv4Address` reads as an address in `block`.

    Notes:
        A block fixes the leading bits and frees the rest, so each octet ranges on its own
        between the octets of the first and last address.
    """
    return _ipv4_tail(int(block.network_address), int(block.broadcast_address))


def _ipv6_block(block: ipaddress.IPv6Network) -> str:
    """Intent:
        The expression of every text `ipaddress.IPv6Address` reads as an address in `block`:
        eight groups; or `::` once, standing for one or more groups that are all zero, with
        up to seven groups around it; the last two groups in either form written as a dotted
        IPv4 address; and an optional scope, `%` then text with no `%` or `/`.

    Notes:
        A block fixes the leading bits and frees the rest, so each group ranges on its own.
        `::` may stand for a group exactly when zero is in that group's range.
    """
    first, last = int(block.network_address), int(block.broadcast_address)
    ranges = [((first >> s) & 0xFFFF, (last >> s) & 0xFFFF) for s in range(112, -1, -16)]
    groups = [_hextet(lo, hi) for lo, hi in ranges]
    tail = _ipv4_tail(first & 0xFFFFFFFF, last & 0xFFFFFFFF)
    forms = [":".join(groups), ":".join([*groups[:6], tail])]
    for before in range(8):
        for after in range(8 - before):
            if any(lo != 0 for lo, _ in ranges[before:8 - after]):
                continue
            head = ":".join(groups[:before]) + "::"
            forms.append(head + ":".join(groups[8 - after:]))
            if after >= 2:
                forms.append(head + ":".join([*groups[8 - after:6], tail]))
    return "(?:" + "|".join(forms) + ")(?:%[^%/]+)?"


def _blocks(regions: tuple[Any, ...], version: int) -> tuple[Any, ...]:
    """Intent:
        The networks `regions` name, each a CIDR block of IP version `version` written by its
        network address, in the order given and each once.

    Raises:
        ValueError: no region is given, or one is not such a block.
    """
    if not regions:
        raise ValueError("within takes at least one CIDR block")
    out = []
    for region in regions:
        example = '"10.0.0.0/8"' if version == 4 else '"2001:db8::/32"'
        if isinstance(region, str) and region != region.strip():
            raise ValueError(f"an IPv{version} block is a CIDR block such as {example}, not {region!r}")
        try:
            block = ipaddress.ip_network(region, strict=True)
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"an IPv{version} block is a CIDR block such as {example}, not {region!r}") from e
        if block.version != version:
            raise ValueError(f"an IPv{version} block is a CIDR block such as {example}, not {region!r}")
        out.append(block)
    return tuple(dict.fromkeys(out))


def _ip_within(base: Any, parse: Any, blocks: tuple[Any, ...], pattern: str,
               spell: Callable[[Any], list[tuple[str, str]]]) -> WithinLanguage:
    """Intent:
        The language of the addresses of `base` inside any of `blocks`. `spell` gives the
        spellings of one address offered at the boundary.
    """
    top = 2 ** blocks[0].max_prefixlen - 1

    def accepts(text: str) -> bool:
        try:
            address = parse(text)
        except ValueError:
            return False
        return any(address in block for block in blocks)

    def generate(rng: random.Random) -> str:
        block = rng.choice(blocks)
        first, last = int(block.network_address), int(block.broadcast_address)
        return str(parse(rng.choice([first, last, rng.randint(first, last), rng.randint(first, last)])))

    members: list[tuple[str, str]] = []
    near: list[tuple[str, str]] = []
    for block in blocks:
        first, last = int(block.network_address), int(block.broadcast_address)
        members += [(str(parse(first)), f"the first address of {block}, its network address"),
                    (str(parse(last)), f"the last address of {block}, its broadcast address")]
        members += spell(parse(first)) + spell(parse(last))
        if first > 0:
            near.append((str(parse(first - 1)), f"the address before {block}"))
        if last < top:
            near.append((str(parse(last + 1)), f"the address after {block}"))
        near += [(str(block), "the block itself, not an address"),
                 (str(parse(first)) + " ", "an address with a trailing space")]
    return _build(base, tuple(str(b) for b in blocks), accepts, generate, members, near, "text",
                  pattern="(?:" + "|".join(dict.fromkeys(pattern.split("\n"))) + ")")


def ipv4_within(*blocks: Any) -> WithinLanguage:
    """The IPv4 addresses inside any of `blocks`, each a CIDR block named
    by its network address (`"10.0.0.0/8"`) or an `IPv4Network`.

    Raises:
        ValueError: no block is given, or one is not an IPv4 CIDR block named by its network
            address.
    """
    nets = _blocks(blocks, 4)
    return _ip_within(IPV4, ipaddress.IPv4Address, nets, "\n".join(_ipv4_block(b) for b in nets),
                      lambda address: [])


def _ipv6_spellings(address: ipaddress.IPv6Address) -> list[tuple[str, str]]:
    """Intent:
        Other spellings of one IPv6 address: every group in full, upper case, the last two
        groups as a dotted IPv4 address, and with a scope.
    """
    groups = [f"{(int(address) >> shift) & 0xFFFF:04x}" for shift in range(112, -1, -16)]
    dotted = str(ipaddress.IPv4Address(int(address) & 0xFFFFFFFF))
    return [(":".join(groups), "every group written in full"),
            (str(address).upper(), "upper-case digits"),
            (":".join([*groups[:6], dotted]), "the last two groups as a dotted IPv4 address"),
            (f"{address}%eth0", "an address with a scope")]


def ipv6_within(*blocks: Any) -> WithinLanguage:
    """The IPv6 addresses inside any of `blocks`, each a CIDR block named
    by its network address (`"2001:db8::/32"`) or an `IPv6Network`, in
    every spelling `ipaddress` reads.

    Raises:
        ValueError: no block is given, or one is not an IPv6 CIDR block named by its network
            address.
    """
    nets = _blocks(blocks, 6)
    return _ip_within(IPV6, ipaddress.IPv6Address, nets, "\n".join(_ipv6_block(b) for b in nets),
                      _ipv6_spellings)


# -- ISO dates: a closed interval -------------------------------------------------

def _weeks(iso_year: int) -> int:
    """Intent:
        The number of weeks, 52 or 53, in an ISO week-numbering year.
    """
    return _dt.date(iso_year, 12, 28).isocalendar()[1]


def _leap(year: int) -> bool:
    """Intent:
        Whether `year` is a leap year of the Gregorian calendar.
    """
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _year_groups(lo: tuple[int, ...], hi: tuple[int, ...], long: Callable[[int], bool],
                 inside: Callable[[bool], list[tuple[int, ...]]]) -> list[tuple[set[int], set[tuple[int, ...]]]]:
    """Intent:
        The points (year, a, b) from `lo` to `hi` in lexicographic order, as groups of years
        that share one set of (a, b): the first year, the last year, and the years between
        split by `long` (a leap year, a 53-week year). `inside(long)` lists every (a, b) of a
        whole year.
    """
    groups: list[tuple[set[int], set[tuple[int, ...]]]] = []
    if lo[0] == hi[0]:
        pairs = {p for p in inside(long(lo[0])) if lo[1:] <= p <= hi[1:]}
        return [({lo[0]}, pairs)]
    groups.append(({lo[0]}, {p for p in inside(long(lo[0])) if p >= lo[1:]}))
    groups.append(({hi[0]}, {p for p in inside(long(hi[0])) if p <= hi[1:]}))
    for flag in (False, True):
        years = {y for y in range(lo[0] + 1, hi[0]) if long(y) == flag}
        if years:
            groups.append((years, set(inside(flag))))
    return [(years, pairs) for years, pairs in groups if pairs]


_MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _calendar_year(leap: bool) -> list[tuple[int, ...]]:
    """Intent:
        Every (month, day) of a year, with 29 February when `leap`.
    """
    return [(m + 1, d) for m, n in enumerate(_MONTH_DAYS)
            for d in range(1, n + (2 if leap and m == 1 else 1))]


def _week_year(long: bool) -> list[tuple[int, ...]]:
    """Intent:
        Every (week, weekday) of an ISO week-numbering year, 53 weeks when `long`, else 52.
    """
    return [(w, d) for w in range(1, (53 if long else 52) + 1) for d in range(1, 8)]


def _date_forms() -> dict[str, bool]:
    """Intent:
        Which ISO 8601 date spellings `date.fromisoformat` reads on the running Python: the
        extended calendar date always, the basic one and the week dates where it reads them.
    """
    def reads(text: str) -> bool:
        try:
            _dt.date.fromisoformat(text)
        except ValueError:
            return False
        return True
    return {"basic": reads("20260928"), "week": reads("2026-W39-1") and reads("2026W39")}


def _date_pattern(lo: _dt.date, hi: _dt.date) -> str:
    """Intent:
        The expression of every text `date.fromisoformat` reads, on the running Python, as a
        date from `lo` to `hi`: `YYYY-MM-DD`, and where read `YYYYMMDD`, `YYYY-Www-D`,
        `YYYYWwwD`, and `YYYY-Www`, `YYYYWww` for the Monday of the week.

    Notes:
        Dates order as (year, month, day) and as (ISO year, week, weekday), so the interval is,
        in either spelling, a part of its first year, a part of its last, and whole years
        between, which differ only by being leap or having 53 weeks.
    """
    forms = _date_forms()
    out: list[str] = []
    calendar = _year_groups((lo.year, lo.month, lo.day), (hi.year, hi.month, hi.day), _leap,
                            _calendar_year)
    for years, pairs in calendar:
        year = finite_pattern(f"{y:04d}" for y in years)
        out.append(year + finite_pattern(f"-{m:02d}-{d:02d}" for m, d in pairs))
        if forms["basic"]:
            out.append(year + finite_pattern(f"{m:02d}{d:02d}" for m, d in pairs))
    if forms["week"]:
        weeks = _year_groups(tuple(lo.isocalendar()), tuple(hi.isocalendar()),
                             lambda y: _weeks(y) == 53, _week_year)
        for years, pairs in weeks:
            year = finite_pattern(f"{y:04d}" for y in years)
            mondays = {w for w, d in pairs if d == 1}
            for dash in ("-", ""):
                words = {f"{dash}W{w:02d}{dash}{d}" for w, d in pairs}
                words |= {f"{dash}W{w:02d}" for w in mondays}
                out.append(year + finite_pattern(words))
    return "(?:" + "|".join(out) + ")"


def _date_spellings(day: _dt.date) -> list[tuple[str, str]]:
    """Intent:
        The ISO 8601 spellings of one date other than `YYYY-MM-DD`, each with a note.
    """
    year, week, weekday = day.isocalendar()
    out = [(f"{day.year:04d}{day.month:02d}{day.day:02d}", "a basic-format date, no hyphens"),
           (f"{year:04d}-W{week:02d}-{weekday}", "a week date"),
           (f"{year:04d}W{week:02d}{weekday}", "a basic-format week date")]
    if weekday == 1:
        out.append((f"{year:04d}-W{week:02d}", "a week with no day, its Monday"))
    return out


def _as_date(bound: Any) -> _dt.date:
    """Intent:
        The date a bound names: a `date` itself, or the text `date.fromisoformat` reads.

    Raises:
        ValueError: the bound is neither.
    """
    if isinstance(bound, _dt.date) and not isinstance(bound, _dt.datetime):
        return bound
    if isinstance(bound, str):
        try:
            return _dt.date.fromisoformat(bound)
        except ValueError as e:
            raise ValueError(f'a date bound is an ISO date such as "2026-01-01", not {bound!r}') from e
    raise ValueError(f'a date bound is an ISO date such as "2026-01-01", not {bound!r}')


def _step(day: _dt.date, days: int) -> _dt.date | None:
    """Intent:
        The date `days` after `day`, or None past the first or last date there is.
    """
    ordinal = day.toordinal() + days
    if _dt.date.min.toordinal() <= ordinal <= _dt.date.max.toordinal():
        return _dt.date.fromordinal(ordinal)
    return None


def iso_date_within(first: Any, last: Any) -> WithinLanguage:
    """The ISO dates from `first` to `last`, both included, in every
    spelling `date.fromisoformat` reads on the running Python. A bound is
    a `date` or ISO date text.

    Raises:
        ValueError: a bound is not a date, or `last` is earlier than `first`.
    """
    lo, hi = _as_date(first), _as_date(last)
    if hi < lo:
        raise ValueError(f"an interval runs from a date to one no earlier, not {lo} to {hi}")

    def accepts(text: str) -> bool:
        try:
            return lo <= _dt.date.fromisoformat(text) <= hi
        except ValueError:
            return False

    def generate(rng: random.Random) -> str:
        day = _dt.date.fromordinal(rng.randint(lo.toordinal(), hi.toordinal()))
        return rng.choice([day.isoformat(), day.isoformat(), *(t for t, _ in _date_spellings(day)
                                                               if accepts(t))])

    members = [(lo.isoformat(), "the first date of the interval"),
               (hi.isoformat(), "the last date of the interval"),
               *_date_spellings(lo), *_date_spellings(hi)]
    near: list[tuple[str, str]] = []
    for day, note in ((_step(lo, -1), "the day before the interval"),
                      (_step(hi, 1), "the day after the interval")):
        if day is not None:
            near += [(day.isoformat(), note), *((t, f"{note}, as {n}") for t, n in _date_spellings(day))]
    near += [(lo.isoformat() + "T00:00:00", "the first date with a time"),
             (lo.isoformat().replace("-", "/"), "the first date with slashes")]
    return _build(ISO_DATE, (lo.isoformat(), hi.isoformat()), accepts, generate, members, near,
                  "time", pattern=_date_pattern(lo, hi))


# -- ISO datetimes: a closed interval ---------------------------------------------

_EPOCH = _dt.datetime(1, 1, 1)
_MICROSECOND = _dt.timedelta(microseconds=1)


def _instant(value: _dt.datetime) -> _dt.timedelta:
    """Intent:
        Where `value` lies on its own line of time, as the time since 0001-01-01T00:00:00: for
        a naive datetime the wall-clock reading, for an aware one the reading at UTC.

    Notes:
        Two datetimes of one awareness order as their instants do. The subtraction is of
        `timedelta`s, so an aware datetime at the edge of the calendar has an instant too.
    """
    offset = value.utcoffset() or _dt.timedelta(0)
    return (value.replace(tzinfo=None) - _EPOCH) - offset


def _at(instant: _dt.timedelta, zone: _dt.tzinfo | None) -> _dt.datetime | None:
    """Intent:
        The datetime at `instant` written in `zone` (naive when None), or None when the
        calendar does not reach it.
    """
    try:
        if zone is None:
            return _EPOCH + instant
        local = _EPOCH + instant + (zone.utcoffset(None) or _dt.timedelta(0))
        return local.replace(tzinfo=zone)
    except OverflowError:
        return None


#: a datetime bound as text: a date, then optionally any one character and a time of hours
#: (00 to 23), hours and minutes, or hours, minutes and seconds with up to six fraction digits, then
#: optionally an offset of hours and minutes (and seconds, and six fraction digits)
_DATETIME_BOUND = re.compile(
    r"(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})"
    r"(?:(?P<between>.)(?P<time>(?:[01][0-9]|2[0-3])(?::[0-9]{2}(?::[0-9]{2}(?:\.(?P<fraction>[0-9]{1,6}))?)?)?)"
    r"(?P<offset>[+-][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]{6})?)?)?)?", re.DOTALL)
_DATETIME_FORM = ('a datetime bound is a date and time such as "2026-01-01T00:00:00", with up to '
                  'six fraction digits and an offset such as "+01:00" if any')


def _as_datetime(bound: Any) -> _dt.datetime:
    """Intent:
        The datetime a bound names: a `datetime` itself, or a text in the one spelling read
        the same on every supported Python: `YYYY-MM-DD`, then optionally a separating
        character and `HH`, `HH:MM` or `HH:MM:SS` with a fraction of one to six digits, then
        optionally an offset `+HH:MM`.

    Raises:
        ValueError: the bound is neither: a spelling only some interpreters'
            `datetime.fromisoformat` read (a `Z`, a comma, the basic or week format, more than
            six fraction digits) is refused on all of them.

    Notes:
        The fraction is filled out to six digits before `datetime.fromisoformat` reads the
        text, since Python 3.10 reads a fraction of three or six digits only.
    """
    if isinstance(bound, _dt.datetime):
        return bound
    found = _DATETIME_BOUND.fullmatch(bound) if isinstance(bound, str) else None
    if found is None:
        raise ValueError(f"{_DATETIME_FORM}, not {bound!r}")
    text = bound
    if found["fraction"] is not None:
        end = found.end("fraction")
        text = bound[:end] + "0" * (6 - len(found["fraction"])) + bound[end:]
    try:
        return _dt.datetime.fromisoformat(text)
    except ValueError as e:
        raise ValueError(f"{_DATETIME_FORM}, not {bound!r}") from e


def _day_of(instant: _dt.timedelta, days: int) -> _dt.date:
    """Intent:
        The date `days` after the date on which `instant` falls when read as a time since
        0001-01-01T00:00:00, held to the first and last dates there are.
    """
    ordinal = 1 + instant.days + days
    return _dt.date.fromordinal(min(max(ordinal, 1), _dt.date.max.toordinal()))


def _datetime_bounds(lo: _dt.datetime, hi: _dt.datetime) -> tuple[str, str]:
    """Intent:
        Two expressions around the datetimes from `lo` to `hi`. The first admits every member:
        any text that starts with a date, in any spelling, from the day before the date of
        `lo`'s instant to the day after the date of `hi`'s. The second admits only members:
        the datetimes of `lo`'s written day, written `YYYY-MM-DDTHH:MM:SS` at `lo`'s own
        offset, from `lo`'s second (the next when `lo` has a fraction) to the end of that
        written day or to `hi`, whichever comes first.

    Notes:
        A member's instant lies between the bounds' instants, and an offset is less than a
        day either way, so a member's written date is at most a day from the date of its
        instant. The second expression is counted on `lo`'s wall clock at the one offset `lo`
        states, so a zone whose offset changes later that day adds no hour to it.
    """
    lo_i, hi_i = _instant(lo), _instant(hi)
    least = _date_pattern(_day_of(lo_i, -1), _day_of(hi_i, 1)) + ".*"
    offset = lo.utcoffset() or _dt.timedelta(0)
    wall = lo.replace(tzinfo=None, microsecond=0)
    first = (wall.hour * 60 + wall.minute) * 60 + wall.second + (1 if lo.microsecond else 0)
    midnight = wall.replace(hour=0, minute=0, second=0)
    words: set[str] = set()
    for s in range(first, 24 * 60 * 60):
        if (midnight - _EPOCH) + _dt.timedelta(seconds=s) - offset > hi_i:
            break
        words.add(f"{s // 3600:02d}:{s // 60 % 60:02d}:{s % 60:02d}")
    if not words:
        return least, "[^\\x00-\\U0010ffff]"
    written = lo.isoformat()[len(lo.replace(tzinfo=None).isoformat()):]
    most = re.escape(lo.date().isoformat()) + "T" + finite_pattern(words) + re.escape(written)
    return least, most


def iso_datetime_within(first: Any, last: Any) -> WithinLanguage:
    """The ISO datetimes from `first` to `last`, both included, in every
    spelling `datetime.fromisoformat` reads on the running Python. A
    bound is a `datetime` or ISO datetime text, and the two are both
    naive or both aware. Between naive bounds the members are naive
    datetimes; between aware bounds they are aware datetimes whose
    instant lies between the bounds', at any offset.

    Raises:
        ValueError: a bound is not a datetime, one is naive and the other aware, or `last` is
            earlier than `first`.
    """
    lo, hi = _as_datetime(first), _as_datetime(last)
    aware = lo.utcoffset() is not None
    if aware != (hi.utcoffset() is not None):
        raise ValueError("the bounds of a datetime interval are both naive or both aware")
    lo_i, hi_i = _instant(lo), _instant(hi)
    if hi_i < lo_i:
        raise ValueError(f"an interval runs from a datetime to one no earlier, not {lo.isoformat()} "
                         f"to {hi.isoformat()}")

    def accepts(text: str) -> bool:
        try:
            value = _dt.datetime.fromisoformat(text)
        except ValueError:
            return False
        if (value.utcoffset() is not None) != aware:
            return False
        return lo_i <= _instant(value) <= hi_i

    zones: list[_dt.tzinfo | None] = [None]
    if aware:
        zones = [_dt.timezone(lo.utcoffset() or _dt.timedelta(0)),
                 _dt.timezone(hi.utcoffset() or _dt.timedelta(0)), _dt.timezone.utc, _dt.timezone(_dt.timedelta(hours=1)),
                 _dt.timezone(_dt.timedelta(hours=-5)), _dt.timezone(_dt.timedelta(hours=5, minutes=30))]

    def generate(rng: random.Random) -> str:
        span = (hi_i - lo_i) // _MICROSECOND
        whole = (hi_i - lo_i) // _dt.timedelta(seconds=1)
        instant = lo_i + rng.choice([rng.randint(0, span) * _MICROSECOND,
                                     _dt.timedelta(seconds=rng.randint(0, whole))])
        value = _at(instant, rng.choice(zones)) or _at(instant, zones[0])
        assert value is not None
        text = value.isoformat()
        return rng.choice([text, text, text.replace("T", " ")])

    members = [(lo.isoformat(), "the first datetime of the interval"),
               (hi.isoformat(), "the last datetime of the interval")]
    near: list[tuple[str, str]] = []
    for zone in zones[2:]:
        for bound, which in ((lo_i, "first"), (hi_i, "last")):
            value = _at(bound, zone)
            if value is not None:
                members.append((value.isoformat(), f"the {which} instant at another offset"))
    for bound, zone, note in ((lo_i - _MICROSECOND, zones[0], "a microsecond before the interval"),
                              (hi_i + _MICROSECOND, zones[-1] if not aware else zones[1],
                               "a microsecond after the interval")):
        value = _at(bound, zone) if bound >= _dt.timedelta(0) else None
        if value is not None:
            near.append((value.isoformat(), note))
    other = lo.replace(tzinfo=None) if aware else lo.replace(tzinfo=_dt.timezone.utc)
    near += [(other.isoformat(), "the first datetime, " + ("naive" if aware else "aware")),
             (lo.date().isoformat() + "T", "a date with no time after the T")]
    if aware:
        near.append((lo.replace(tzinfo=None).isoformat() + "+01:00" if lo.utcoffset() == _dt.timedelta(0)
                     else lo.replace(tzinfo=_dt.timezone.utc).isoformat(),
                     "the first datetime's wall clock at another offset"))
    return _build(ISO_DATETIME, (lo.isoformat(), hi.isoformat()), accepts, generate, members, near,
                  "time", bounds=_datetime_bounds(lo, hi))


# -- URLs: an origin, or a path prefix under one ----------------------------------

_DEFAULT_PORTS = {"http": 80, "https": 443}
#: a `..` path segment, plain or percent-encoded
_CLIMB = re.compile(r"(?:\.|%2[eE]){2}")
_CLIMBS = tuple(a + b for a in (".", "%2e", "%2E") for b in (".", "%2e", "%2E"))
#: the characters a path segment under a prefix never holds, as a class body
_NOT_SEGMENT = "".join(map(chr, range(0x21))) + "/?#\\"
_REST = r"(?:[/?#][^\x00-\x20]*)?"
_QUERY = r"(?:[?#][^\x00-\x20]*)?"


def _either_case(text: str) -> str:
    """Intent:
        The expression of `text` with each letter in either case.
    """
    return "".join(f"[{c.upper()}{c.lower()}]" if c.isalpha() else re.escape(c) for c in text)


@dataclass(frozen=True)
class _UrlRegion:
    """An origin (scheme and host in lower case, port, the scheme's own
    when none was written, or None) and a path prefix with no trailing
    slash, empty for the whole origin."""
    scheme: str
    host: str
    port: int | None
    prefix: str

    def text(self) -> str:
        """The region as a URL: the port written only when it is not the
        scheme's own."""
        port = "" if self.port is None or self.port == _DEFAULT_PORTS.get(self.scheme) else f":{self.port}"
        return f"{self.scheme}://{self.host}{port}{self.prefix}"

    def pattern(self) -> str:
        """The expression of every URL text in the region."""
        own = _DEFAULT_PORTS.get(self.scheme)
        port = ""
        if self.port is not None:
            digits = str(self.port)
            zeros = f"0{{0,{5 - len(digits)}}}" if len(digits) < 5 else ""
            port = f"(?::{zeros}{digits})" + ("?" if self.port == own else "")
        head = _either_case(self.scheme) + "://" + _either_case(self.host) + port
        if not self.prefix:
            return head + _REST
        segment = finite_complement(_CLIMBS, excluded=_NOT_SEGMENT)
        return head + re.escape(self.prefix) + "(?:/" + segment + ")*" + _QUERY

    def holds(self, parts: Any) -> bool:
        """Whether a URL's parts, as `url_parts` reads them, lie in the
        region."""
        port = parts.port if parts.port is not None else _DEFAULT_PORTS.get(parts.scheme)
        if "@" in parts.netloc or (parts.scheme, parts.hostname, port) != (self.scheme, self.host, self.port):
            return False
        if not self.prefix:
            return True
        path = parts.path
        if "\\" in path or any(_CLIMB.fullmatch(s) for s in path.split("/")):
            return False
        return bool(path == self.prefix or path.startswith(self.prefix + "/"))


_URL_FORM = 'a URL with no user, query or fragment such as "https://example.com/api"'


def _url_region(region: Any) -> _UrlRegion:
    """Intent:
        The region a URL names: its origin, and its path as a prefix unless the path is empty
        or `/`.

    Raises:
        ValueError: `region` is not in `L[url]`, names a user part, a query or a fragment, or
            its path holds a backslash or a `..` segment, plain or percent-encoded.
    """
    parts = url_parts(region)
    if parts is None or "@" in parts.netloc or "?" in region or "#" in region:
        raise ValueError(f"a URL region is {_URL_FORM}, not {region!r}")
    if "\\" in parts.path or any(_CLIMB.fullmatch(s) for s in parts.path.split("/")):
        raise ValueError(f"a URL region names no '..' segment and no backslash, not {region!r}")
    port = parts.port if parts.port is not None else _DEFAULT_PORTS.get(parts.scheme)
    return _UrlRegion(parts.scheme, parts.hostname or "", port, parts.path.rstrip("/"))


def url_within(*regions: str) -> WithinLanguage:
    """The URLs inside any of `regions`. A region is a URL with no user
    part, query or fragment: with no path, or `/`, it is the origin, every
    URL of that scheme, host and port that names no user; with a path it
    is the URLs of that origin whose path is that path or continues it
    after a `/`, with no backslash and no `..` segment, plain or
    percent-encoded.

    Raises:
        ValueError: no region is given, or one is not such a URL.
    """
    if not regions:
        raise ValueError("within takes at least one URL")
    found = tuple(dict.fromkeys(_url_region(r) for r in regions))

    def accepts(text: str) -> bool:
        parts = url_parts(text)
        return parts is not None and any(r.holds(parts) for r in found)

    def generate(rng: random.Random) -> str:
        r = rng.choice(found)
        port = rng.choice(["", "", f":{r.port}"]) if r.port == _DEFAULT_PORTS.get(r.scheme) else (
            "" if r.port is None else f":{r.port}")
        scheme, host = rng.choice([(r.scheme, r.host), (r.scheme, r.host), (r.scheme.upper(), r.host.upper())])
        path = "".join("/" + rng.choice(["a", "v1", "x.y", "%20", ".", "..."]) for _ in range(rng.randint(0, 3)))
        tail = rng.choice(["", "", "/", "?q=1", "#top", "?next=http://evil.example/"])
        return f"{scheme}://{host}{port}{r.prefix}{path}{tail}"

    members: list[tuple[str, str]] = []
    near: list[tuple[str, str]] = []
    for r in found:
        own = r.text()
        origin, rest = own[:len(own) - len(r.prefix)], r.prefix
        after = origin[len(r.scheme) + 3:]
        members += [(own, "the region itself"), (own + "/", "the region with a trailing slash"),
                    (r.scheme.upper() + "://" + after.upper() + rest, "an upper-case scheme and host"),
                    (own + "?next=http://evil.example/", "another URL in the query"),
                    (own + "/.", "a '.' segment"), (own + "/...", "a segment of three dots")]
        if r.port is not None and r.port == _DEFAULT_PORTS.get(r.scheme):
            members.append((f"{r.scheme}://{r.host}:{r.port}{rest}", "the scheme's own port, written out"))
        other = "http" if r.scheme != "http" else "https"
        near += [(f"{r.scheme}://user@{after}{rest}", "a user part"),
                 (f"{r.scheme}://{r.host}@evil.example{rest}", "the host as a user part of another host"),
                 (f"{r.scheme}://{r.host}:8443{rest}" if r.port != 8443 else f"{r.scheme}://{r.host}:8444{rest}",
                  "another port"),
                 (f"{r.scheme}://{r.host}.evil.example{rest}", "a host that starts with the region's host"),
                 (f"{r.scheme}://{r.host}puter{rest}", "a host that starts with the region's host, no dot"),
                 (f"{other}://{after}{rest}", "another scheme"),
                 (f"{r.scheme}://evil.example/{own}", "the region carried in another URL's path"),
                 (f"{r.scheme}://{r.host}\\@evil.example{rest}", "a backslash before an at sign")]
        if r.prefix:
            near += [(own + "/../admin", "a climb out of the prefix"),
                     (own + "/%2e%2e/admin", "a percent-encoded climb out of the prefix"),
                     (own + "v2", "a sibling path that starts with the prefix"),
                     (own + "\\..\\admin", "a climb written with backslashes"),
                     (origin + "/", "the origin's root, above the prefix")]
    pattern = "(?:" + "|".join(r.pattern() for r in found) + ")"
    return _build(URL, tuple(r.text() for r in found), accepts, generate, members, near, "text",
                  pattern=pattern)


# -- the word ----------------------------------------------------------------------

def _is_root(text: str) -> bool:
    """Intent:
        Whether `text` is an absolute path a path language takes as a root.
    """
    try:
        _normal_root(text)
    except ValueError:
        return False
    return True


def _is_block(version: int) -> Callable[[str], bool]:
    """Intent:
        A test of whether text is a CIDR block of IP version `version`, named by its network
        address.
    """
    def test(text: str) -> bool:
        try:
            _blocks((text,), version)
        except ValueError:
            return False
        return True
    return test


def _parses(parse: Callable[[Any], Any]) -> Callable[[str], bool]:
    """Intent:
        A test of whether `parse` reads text without a ValueError.
    """
    def test(text: str) -> bool:
        try:
            parse(text)
        except ValueError:
            return False
        return True
    return test


@dataclass(frozen=True)
class BoundaryKind:
    """What `within` means for one base language. `base` is the
    language's name, `noun` what a member is, `bounds` what the word
    bounds it to, `form` the form of one argument, with an example,
    `example` complete arguments for the word, `count` how many
    arguments it takes (None: one or more, a union), `fits` whether one
    argument has the form, `build` the constructor, and `registered`
    whether `L[base]` resolves by name in a claim."""
    base: str
    noun: str
    bounds: str
    form: str
    example: tuple[str, ...]
    count: int | None
    fits: Callable[[str], bool]
    build: Callable[..., Any]
    registered: bool = True


#: the base languages `within` has a meaning for, by name, in the order a guess tries them
WITHIN: dict[str, BoundaryKind] = {kind.base: kind for kind in (
    BoundaryKind("path", "a path", "a subtree", 'an absolute path such as "/workspace"',
                 ("/workspace",), None, _is_root, path_within),
    BoundaryKind("ipv4", "an IPv4 address", "an address block", 'a CIDR block such as "10.0.0.0/8"',
                 ("10.0.0.0/8",), None, _is_block(4), ipv4_within),
    BoundaryKind("ipv6", "an IPv6 address", "an address block", 'a CIDR block such as "2001:db8::/32"',
                 ("2001:db8::/32",), None, _is_block(6), ipv6_within),
    BoundaryKind("iso_date", "a date", "an interval of dates", 'an ISO date such as "2026-01-01"',
                 ("2026-01-01", "2026-12-31"), 2, _parses(_as_date), iso_date_within),
    BoundaryKind("iso_datetime", "a datetime", "an interval of datetimes",
                 'an ISO datetime such as "2026-01-01T00:00:00"',
                 ("2026-01-01T00:00:00", "2026-12-31T23:59:59"), 2, _parses(_as_datetime),
                 iso_datetime_within),
    BoundaryKind("url", "a URL", "an origin or a path prefix", _URL_FORM,
                 ("https://example.com/api",), None, _parses(_url_region), url_within, registered=False),
)}


def claim_text(base: str, word: str, arguments: tuple[str, ...]) -> str:
    """Intent:
        The complete domain text of `base` refined by a predicate word applied to quoted
        arguments, as a claim writes it: `L[path, within ("/workspace")]`.
    """
    return f"L[{base}, {word} (" + ", ".join(_quoted(a) for a in arguments) + ")]"


def within_examples() -> dict[str, str]:
    """Intent:
        One complete example of the word for each base language it has a meaning for and a
        claim can name, by the language's name.
    """
    return {kind.base: claim_text(kind.base, "within", kind.example)
            for kind in WITHIN.values() if kind.registered}


def within_refusal(base: str, arguments: tuple[str, ...]) -> str | None:
    """Intent:
        Why `within` with `arguments` is refused on the language named `base`, or None when it
        is not: the word has no meaning for that language, the number of arguments is not the
        one the language takes, or an argument has not the expected form, which is named.
    """
    kind = WITHIN.get(base)
    if kind is None:
        return f"'within' has no meaning for L[{base}]: it bounds " + _listed(
            [k.noun for k in WITHIN.values() if k.registered])
    if kind.count is not None and len(arguments) != kind.count:
        return (f"within on L[{base}] takes {kind.count} arguments, {kind.bounds}, not "
                f"{len(arguments)}: {claim_text(base, 'within', kind.example)}")
    if not arguments:
        return f"within on L[{base}] takes at least one argument: {claim_text(base, 'within', kind.example)}"
    for argument in arguments:
        if not isinstance(argument, str) or not kind.fits(argument):
            return (f"within ({_quoted(str(argument))}) is not {kind.bounds} for L[{base}]: it expects "
                    f"{kind.form}")
    try:
        kind.build(*arguments)
    except ValueError as e:
        return f"within on L[{base}]: {e}"
    return None


def _listed(nouns: list[str]) -> str:
    """Intent:
        The nouns as an English list ending in `or`.
    """
    return nouns[0] if len(nouns) == 1 else ", ".join(nouns[:-1]) + " or " + nouns[-1]


def suggest_within(base: str, arguments: tuple[str, ...]) -> tuple[str, ...]:
    """Intent:
        The complete domain texts a claim that wrote `within` with `arguments` on the language
        named `base` most likely meant, best first, when that use is refused; empty when it
        is not refused or nothing fits.

    Notes:
        A base language the arguments fit, other than `base`, is suggested with the arguments
        as given: an absolute path suggests `L[path, within (...)]`, a CIDR block the IP
        language of its version, two dates `L[iso_date, within (...)]`. A base whose own
        arguments have the wrong form or number is suggested with its example. On a base the
        word has no meaning for, one argument also suggests the text that begins with it:
        `L[base, starts with (...)]`. Only languages a claim can name are suggested.
    """
    if within_refusal(base, arguments) is None:
        return ()
    out: list[str] = []
    for kind in WITHIN.values():
        if kind.registered and kind.base != base and within_refusal(kind.base, arguments) is None:
            out.append(claim_text(kind.base, "within", arguments))
    if base in WITHIN:
        if WITHIN[base].registered:
            out.append(claim_text(base, "within", WITHIN[base].example))
    elif len(arguments) == 1 and isinstance(arguments[0], str):
        out.append(claim_text(base, "starts with", arguments))
    return tuple(out)


#: whether the word is also read in its keyword spelling, `within "/root"`, one argument
#: after the word with no brackets
WITHIN_KEYWORD = True

_WORD = re.compile(r"\s*within\s*", re.IGNORECASE)
_ARGUMENT = re.compile(r'\s*"((?:[^"\\]|\\.)*)"\s*')


def within_arguments(text: str) -> tuple[str, ...]:
    """Intent:
        The arguments of the word as written after a base language, in either spelling: the
        bracket form `within ("/a", "/b")`, or the keyword form `within "/a"` with one
        argument. Inside the quotes a backslash makes the next character itself.

    Raises:
        ValueError: the text is not the word followed by quoted arguments in one of the two
            spellings.
    """
    word = _WORD.match(text)
    refusal = ValueError(f'within is written within ("/root") or within "/root", not {text!r}')
    if word is None:
        raise refusal
    rest = text[word.end():].strip()
    bracketed = rest.startswith("(") and rest.endswith(")")
    if bracketed:
        rest = rest[1:-1]
    found: list[str] = []
    at = 0
    while True:
        argument = _ARGUMENT.match(rest, at)
        if argument is None:
            raise refusal
        found.append(re.sub(r"\\(.)", r"\1", argument.group(1), flags=re.DOTALL))
        at = argument.end()
        if at >= len(rest):
            break
        if not bracketed or rest[at] != ",":
            raise refusal
        at += 1
    return tuple(found)


@functools.lru_cache(maxsize=64)
def _built(base: str, regions: tuple[str, ...]) -> Any:
    """Intent:
        The language named `base` within `regions`.

    Raises:
        ValueError: `within` has no meaning for `base`, or a region has not the form it takes.
    """
    kind = WITHIN.get(base)
    if kind is None:
        raise ValueError(within_refusal(base, regions))
    return kind.build(*regions)


def _reads(base: str, text: str, *regions: str) -> bool:
    """Intent:
        Whether `text` is in the language named `base` within `regions`, by the standard
        library's reading of it.

    Claims:
        the_whole_ipv4_space_holds_every_address: for text in L[ipv4], f("ipv4", text, "0.0.0.0/0") == True
        the_whole_ipv6_space_holds_every_address: for text in L[ipv6], f("ipv6", text, "::/0") == True
        every_date_is_between_the_first_and_the_last: for text in L[iso_date], f("iso_date", text, "0001-01-01", "9999-12-31") == True
        an_address_of_a_block_is_in_the_block_around_it: for text in L[mathema_language.text.within._INNER_IPV4], f("ipv4", text, "10.0.0.0/8") == True
        an_address_of_a_block_is_not_in_its_other_half: for text in L[mathema_language.text.within._INNER_IPV4], f("ipv4", text, "10.128.0.0/9") == False
        an_ipv6_address_of_a_block_is_in_the_block_around_it: for text in L[mathema_language.text.within._INNER_IPV6], f("ipv6", text, "2001:db8::/32") == True
        a_path_of_a_subtree_is_under_its_parent: for text in L[mathema_language.text.within._INNER_PATH], f("path", text, "/workspace") == True
        a_date_of_a_month_is_in_its_year: for text in L[mathema_language.text.within._INNER_DATES], f("iso_date", text, "2026-01-01", "2026-12-31") == True
        a_date_of_march_is_not_in_april: for text in L[mathema_language.text.within._INNER_DATES], f("iso_date", text, "2026-04-01", "2026-04-30") == False
        a_url_under_a_prefix_is_in_its_origin: for text in L[mathema_language.text.within._INNER_URL], f("url", text, "https://example.com") == True
        the_addresses_beside_a_block_are_outside_it: for text in {"10.0.255.255", "10.2.0.0", "9.255.255.255", "10.1.0.0/16", "010.1.0.0", "10.1.0.0 "}, f("ipv4", text, "10.1.0.0/16") == False
        the_paths_beside_a_root_are_outside_it: for text in {"/workspace2", "/workspac", "/workspace/../etc", "/", "//workspace", ""}, f("path", text, "/workspace") == False
        the_urls_beside_a_prefix_are_outside_it: for text in {"https://user@example.com/api", "https://example.com@evil.example/api", "https://example.com:8443/api", "https://example.com.evil.example/api", "https://example.com/apiv2", "https://example.com/api/../admin", "https://example.com/api/%2e%2e/admin", "http://example.com/api"}, f("url", text, "https://example.com/api") == False
        the_days_beside_an_interval_are_outside_it: for text in {"2026-02-28", "2026-04-01", "2026-W09-6", "20260401", "2026-03-01T00:00:00"}, f("iso_date", text, "2026-03-01", "2026-03-31") == False

    Raises:
        ValueError: `within` has no meaning for `base`, or a region has not the form it takes.
    """
    return bool(_built(base, regions).contains(text))


def _escapes(base: str, text: str, inner: str, outer: str) -> bool:
    """Intent:
        Whether `text` is in the language named `base` within the one region `inner` and not
        within the one region `outer`: a witness that `inner` is not inside `outer`.

    Claims:
        no_address_of_a_block_escapes_the_block_around_it: for text in L[mathema_language.text.within._INNER_IPV4], f("ipv4", text, "10.1.0.0/16", "10.0.0.0/8") == False
        every_address_of_a_block_escapes_its_other_half: for text in L[mathema_language.text.within._INNER_IPV4], f("ipv4", text, "10.1.0.0/16", "10.128.0.0/9") == True
        an_address_escapes_the_smaller_block: f("ipv4", "10.2.0.0", "10.0.0.0/8", "10.1.0.0/16") == True
        no_path_of_a_subtree_escapes_its_parent: for text in L[mathema_language.text.within._INNER_PATH], f("path", text, "/workspace/src", "/workspace") == False
        a_path_escapes_the_subtree: f("path", "/workspace/README.md", "/workspace", "/workspace/src") == True
        a_sibling_prefix_is_not_under_the_root: f("path", "/workspace2", "/", "/workspace") == True
        no_address_escapes_the_ipv6_block_around_it: for text in L[mathema_language.text.within._INNER_IPV6], f("ipv6", text, "2001:db8:1::/48", "2001:db8::/32") == False
        no_url_under_a_prefix_escapes_its_origin: for text in L[mathema_language.text.within._INNER_URL], f("url", text, "https://example.com/api", "https://example.com") == False

    Raises:
        ValueError: `within` has no meaning for `base`, or a region has not the form it takes.
    """
    return _reads(base, text, inner) and not _reads(base, text, outer)


def _matches(base: str, text: str, *regions: str) -> bool:
    """Intent:
        Whether `text` is in the language named `base` within `regions`, by the language's
        pattern read in full.

    Claims:
        the_ipv4_pattern_admits_the_addresses_of_a_block_inside: for text in L[mathema_language.text.within._INNER_IPV4], f("ipv4", text, "10.0.0.0/8") == True
        the_ipv4_pattern_agrees_on_half_of_all_addresses: let reads = mathema_language.text.within._reads, for text in L[ipv4], f("ipv4", text, "128.0.0.0/1") == reads("ipv4", text, "128.0.0.0/1")
        the_ipv4_pattern_refuses_the_text_beside_a_block: for text in {"10.0.255.255", "10.2.0.0", "9.255.255.255", "10.1.0.0/16", "010.1.0.0", "10.1.0.0 ", "10.1.0", "10.1.0.0.0"}, f("ipv4", text, "10.1.0.0/16") == False
        the_ipv6_pattern_admits_every_spelling_of_a_block_inside: for text in L[mathema_language.text.within._INNER_IPV6], f("ipv6", text, "2001:db8::/32") == True
        the_ipv6_pattern_agrees_on_half_of_all_addresses: let reads = mathema_language.text.within._reads, for text in L[ipv6], f("ipv6", text, "8000::/1") == reads("ipv6", text, "8000::/1")
        the_date_pattern_admits_the_dates_of_a_month_inside: for text in L[mathema_language.text.within._INNER_DATES], f("iso_date", text, "2026-01-01", "2026-12-31") == True
        the_date_pattern_agrees_on_dates_either_side_of_a_bound: let reads = mathema_language.text.within._reads, for text in L[iso_date], f("iso_date", text, "0001-01-01", "5000-06-15") == reads("iso_date", text, "0001-01-01", "5000-06-15")
        the_date_pattern_refuses_the_days_beside_an_interval: for text in {"2026-02-28", "2026-04-01", "2026-W09-6", "20260401", "2026-03-01T00:00:00", "2026-03-32", "2026-3-01"}, f("iso_date", text, "2026-03-01", "2026-03-31") == False
        the_url_pattern_admits_the_urls_under_a_prefix: for text in L[mathema_language.text.within._INNER_URL], f("url", text, "https://example.com/api") == True
        the_url_pattern_refuses_the_urls_beside_a_prefix: for text in {"https://user@example.com/api", "https://example.com@evil.example/api", "https://example.com:8443/api", "https://example.com.evil.example/api", "https://example.com/apiv2", "https://example.com/api/../admin", "https://example.com/api/%2e%2e/admin", "http://example.com/api"}, f("url", text, "https://example.com/api") == False

    Raises:
        ValueError: `within` has no meaning for `base`, a region has not the form it takes, or
            the language states no pattern.
    """
    pattern = _built(base, regions).pattern
    if not isinstance(pattern, str):
        raise ValueError(f"L[{base}] within {regions!r} states no pattern")
    return re.fullmatch(pattern, text) is not None


def _in_term(base: str, text: str, *regions: str) -> bool:
    """Intent:
        Whether `text` is in the regular-language term of the language named `base` within
        `regions`: in its language where the term is exact, else in its `at_least` bound.

    Claims:
        the_ipv4_term_admits_the_addresses_of_a_block_inside: for text in L[mathema_language.text.within._INNER_IPV4], f("ipv4", text, "10.0.0.0/8") == True
        the_ipv4_term_agrees_on_half_of_all_addresses: let reads = mathema_language.text.within._reads, for text in L[ipv4], f("ipv4", text, "128.0.0.0/1") == reads("ipv4", text, "128.0.0.0/1")
        the_date_term_agrees_on_dates_either_side_of_a_bound: let reads = mathema_language.text.within._reads, for text in L[iso_date], f("iso_date", text, "0001-01-01", "5000-06-15") == reads("iso_date", text, "0001-01-01", "5000-06-15")
        the_path_term_agrees_with_the_pattern_on_paths: let reads = mathema_language.text.within._reads, for text in L[path], f("path", text, "/workspace") == reads("path", text, "/workspace")
        the_path_term_refuses_the_paths_beside_a_root: for text in {"/workspace2", "/workspac", "/workspace/../etc", "/", "//workspace", ""}, f("path", text, "/workspace") == False
        the_datetime_bound_holds_every_member_at_any_offset: for text in L[mathema_language.text.within._OFFSET_DATETIMES], f("iso_datetime", text, "2026-01-02T00:30:00+14:00", "2026-01-05T00:00:00+14:00") == True
        the_datetime_bound_holds_the_first_instant_two_written_days_away: f("iso_datetime", "2025-12-31T22:30:00-12:00", "2026-01-02T00:30:00+14:00", "2026-01-05T00:00:00+14:00") == True

    Raises:
        ValueError: `within` has no meaning for `base`, or a region has not the form it takes.
    """
    return _regular.member(_built(base, regions).definition(), text, "at_least")


def _certain(text: str, first: str, last: str) -> bool:
    """Intent:
        Whether `text` is in the `at_most` bound of the datetime interval from `first` to
        `last`: a text the term states is certainly a member.

    Claims:
        what_is_certain_between_naive_bounds_is_a_member: let reads = mathema_language.text.within._reads, for text in L[mathema_language.text.within._CERTAIN_NAIVE], reads("iso_datetime", text, "2026-11-19T09:00:00.5", "2026-11-19T17:30:00") == True
        what_is_certain_between_aware_bounds_is_a_member: let reads = mathema_language.text.within._reads, for text in L[mathema_language.text.within._CERTAIN_AWARE], reads("iso_datetime", text, "2026-01-02T00:30:00+14:00", "2026-01-05T00:00:00+14:00") == True
        the_certain_texts_are_in_the_bound: for text in L[mathema_language.text.within._CERTAIN_NAIVE], f(text, "2026-11-19T09:00:00.5", "2026-11-19T17:30:00") == True
        nothing_is_certain_past_the_bounds_or_the_day: for text in {"2026-11-19T09:00:00", "2026-11-19T17:30:01", "2026-11-19T24:00:00", "2026-11-20T09:00:01", "2026-11-19T12:00:00+00:00", "2026-11-19T12:00:00\\n"}, f(text, "2026-11-19T09:00:00.5", "2026-11-19T17:30:00") == False
        a_whole_second_inside_is_certain: for text in {"2026-11-19T09:00:01", "2026-11-19T12:00:00", "2026-11-19T17:30:00"}, f(text, "2026-11-19T09:00:00.5", "2026-11-19T17:30:00") == True

    Raises:
        ValueError: a bound is not a datetime, or the bounds are not in order.
    """
    return _regular.member(_built("iso_datetime", (first, last)).definition(), text, "at_most")


def within(language: Any, *regions: Any) -> Any:
    """The members of `language` inside `regions`, as the base language
    reads a region: a subtree for `L[path]`, a CIDR block for `L[ipv4]`
    and `L[ipv6]`, the two bounds of a closed interval for `L[iso_date]`
    and `L[iso_datetime]`, an origin or path prefix for `L[url]`.

    Raises:
        ValueError: `within` has no meaning for `language`, or a region has not the form the
            language takes.
        TypeError: an interval is given other than two bounds.
    """
    for base, kind in ((PATH, "path"), (IPV4, "ipv4"), (IPV6, "ipv6"), (ISO_DATE, "iso_date"),
                       (ISO_DATETIME, "iso_datetime"), (URL, "url")):
        if language is base:
            return WITHIN[kind].build(*regions)
    name = getattr(language, "name", language)
    raise ValueError(within_refusal(str(name), tuple(map(str, regions))))


__all__ = ["WITHIN", "WITHIN_KEYWORD", "within_arguments", "BoundaryKind", "WithinLanguage", "claim_text", "ipv4_within", "ipv6_within",
           "iso_date_within", "iso_datetime_within", "suggest_within", "url_within", "within",
           "within_examples", "within_refusal"]


#: languages the claims on this module quantify over, each named by its dotted path
_INNER_IPV4 = ipv4_within("10.1.0.0/16")
_INNER_IPV6 = ipv6_within("2001:db8:1::/48")
_INNER_PATH = path_within("/workspace/src")
_INNER_DATES = iso_date_within("2026-03-01", "2026-03-31")
_INNER_URL = url_within("https://example.com/api")
_OFFSET_DATETIMES = iso_datetime_within("2026-01-02T00:30:00+14:00", "2026-01-05T00:00:00+14:00")


def _certain_language(language: WithinLanguage) -> TextLanguage:
    """Intent:
        The text language of a datetime interval's `at_most` bound: the texts its term states
        are certainly members, drawn from the bound's own expression.
    """
    from .regex import draw_matching

    assert language.bounds is not None
    most = language.bounds[1]
    return TextLanguage(
        f"certain of ({language.name})", level="regular",
        accepts=lambda text: re.fullmatch(most, text) is not None,
        generate=lambda rng: draw_matching(rng, most) or "")


_CERTAIN_NAIVE = _certain_language(iso_datetime_within("2026-11-19T09:00:00.5", "2026-11-19T17:30:00"))
_CERTAIN_AWARE = _certain_language(_OFFSET_DATETIMES)
