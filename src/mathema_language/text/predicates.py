# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The predicate languages: exactly the strings a whole-string test
accepts, each test a standard-library parser so membership is the
running Python's own reading and never a regex written here. Each has a
generator of members, since drawing characters would rarely land in a
language this narrow.
"""
from __future__ import annotations

import base64
import binascii
import datetime as _dt
import ipaddress
import json
import random
import re
import shlex
import string
import sys
import uuid
from collections.abc import Callable

from .._surface import HazardValue
from ._kit import TextLanguage

_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_SHELL_SAFE_CHARS = string.ascii_letters + string.digits + "@%_-+=:,./"


def _is_json(s: str) -> bool:
    """Intent:
        Whether `json.loads` reads `s`.

    Notes:
        A document nested past the interpreter's recursion limit is one it does not read.
    """
    try:
        json.loads(s)
    except (ValueError, RecursionError):
        return False
    return True


def _is_uuid(s: str) -> bool:
    """Intent:
        Whether `uuid.UUID` reads `s`, in any of its hyphenated, bare, braced or urn forms.
    """
    try:
        uuid.UUID(s)
    except ValueError:
        return False
    return True


def _is_iso_date(s: str) -> bool:
    """Intent:
        Whether `date.fromisoformat` reads `s` on the running Python.
    """
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        return False
    return True


def _is_iso_datetime(s: str) -> bool:
    """Intent:
        Whether `datetime.fromisoformat` reads `s` on the running Python.
    """
    try:
        _dt.datetime.fromisoformat(s)
    except ValueError:
        return False
    return True


def _is_ipv4(s: str) -> bool:
    """Intent:
        Whether `ipaddress.IPv4Address` reads `s`.
    """
    try:
        ipaddress.IPv4Address(s)
    except ValueError:
        return False
    return True


def _is_ipv6(s: str) -> bool:
    """Intent:
        Whether `ipaddress.IPv6Address` reads `s`.
    """
    try:
        ipaddress.IPv6Address(s)
    except ValueError:
        return False
    return True


def _is_base64(s: str) -> bool:
    """Intent:
        Whether `s` is strict base64: `b64decode(validate=True)` reads it and encoding the
        bytes gives back exactly `s`.
    """
    try:
        raw = base64.b64decode(s, validate=True)
    except (binascii.Error, ValueError):
        return False
    return base64.b64encode(raw).decode("ascii") == s


def _is_hex(s: str) -> bool:
    """Intent:
        Whether `bytes.fromhex` reads `s`.
    """
    try:
        bytes.fromhex(s)
    except ValueError:
        return False
    return True


def _is_slug(s: str) -> bool:
    """Intent:
        Whether `s` is lower-case words of letters and digits joined by single hyphens.
    """
    return _SLUG.fullmatch(s) is not None


def _is_shell_safe(s: str) -> bool:
    """Intent:
        Whether `s` is non-empty and `shlex.quote` leaves it unchanged.
    """
    return s != "" and shlex.quote(s) == s


def _generate_identifier(rng: random.Random) -> str:
    """Intent:
        A random Python identifier: an ascii letter or underscore, then up to eleven ascii
        letters, digits or underscores.
    """
    first = rng.choice(string.ascii_letters + "_")
    rest = "".join(rng.choice(string.ascii_letters + string.digits + "_")
                   for _ in range(rng.randint(0, 11)))
    return first + rest


def _generate_json(rng: random.Random) -> str:
    """Intent:
        A random JSON document of scalars, arrays and objects nested at most three levels,
        written with non-ascii characters left unescaped.
    """
    def value(depth: int) -> object:
        choice = rng.random()
        if depth > 1 or choice < 0.4:
            return rng.choice([0, 1, -1, 1.5, 1e300, True, False, None,
                               "", "a", "caf\u00e9", "\u65e5\u672c\u8a9e"])
        if choice < 0.7:
            return [value(depth + 1) for _ in range(rng.randint(0, 3))]
        return {rng.choice(["a", "b", "key", ""]): value(depth + 1)
                for _ in range(rng.randint(0, 3))}
    return json.dumps(value(0), ensure_ascii=False)


def _generate_uuid(rng: random.Random) -> str:
    """Intent:
        A random UUID in its hyphenated form, from 128 random bits.
    """
    return str(uuid.UUID(int=rng.getrandbits(128)))


def _generate_iso_date(rng: random.Random) -> str:
    """Intent:
        A random ISO 8601 date (`YYYY-MM-DD`) in years 1 to 9999, day at most 28.
    """
    return _dt.date(rng.randint(1, 9999), rng.randint(1, 12),
                    rng.randint(1, 28)).isoformat()


def _generate_iso_datetime(rng: random.Random) -> str:
    """Intent:
        A random ISO 8601 datetime, naive, in UTC or at a whole-hour offset, with or without
        microseconds.
    """
    tz = rng.choice([None, _dt.timezone.utc,
                     _dt.timezone(_dt.timedelta(hours=rng.randint(-12, 14)))])
    return _dt.datetime(rng.randint(1, 9999), rng.randint(1, 12),
                        rng.randint(1, 28), rng.randint(0, 23),
                        rng.randint(0, 59), rng.randint(0, 59),
                        rng.choice([0, rng.randint(0, 999999)]),
                        tzinfo=tz).isoformat()


def _generate_ipv4(rng: random.Random) -> str:
    """Intent:
        A random IPv4 address in dotted-decimal form.
    """
    return str(ipaddress.IPv4Address(rng.getrandbits(32)))


def _generate_ipv6(rng: random.Random) -> str:
    """Intent:
        A random IPv6 address in its compressed form.
    """
    return str(ipaddress.IPv6Address(rng.getrandbits(128)))


def _generate_base64(rng: random.Random) -> str:
    """Intent:
        The standard base64 encoding of up to 24 random bytes.
    """
    raw = bytes(rng.getrandbits(8) for _ in range(rng.randint(0, 24)))
    return base64.b64encode(raw).decode("ascii")


def _generate_hex(rng: random.Random) -> str:
    """Intent:
        An even-length string of up to 24 hex digits in mixed case.
    """
    return "".join(rng.choice("0123456789abcdefABCDEF")
                   for _ in range(2 * rng.randint(0, 12)))


def _generate_slug(rng: random.Random) -> str:
    """Intent:
        One to four random words of lower-case letters and digits, joined by hyphens.
    """
    words = [
        "".join(rng.choice(string.ascii_lowercase + string.digits)
                for _ in range(rng.randint(1, 8)))
        for _ in range(rng.randint(1, 4))]
    return "-".join(words)


def _generate_shell_safe(rng: random.Random) -> str:
    """Intent:
        A random string of one to twelve characters a shell reads literally.
    """
    return "".join(rng.choice(_SHELL_SAFE_CHARS)
                   for _ in range(rng.randint(1, 12)))


#: what `str.isidentifier` accepts
IDENTIFIER = TextLanguage(
    "identifier", level="predicate", accepts=str.isidentifier,
    generate=_generate_identifier,
    pool=string.ascii_letters + string.digits + "_", outside_pool=" -.1",
    extra_hazards=(HazardValue("text", "_", "a lone underscore"),
                   HazardValue("text", "\u00e9t\u00e9", "letters outside ascii"),
                   HazardValue("text", "\u2160", "a Roman numeral letter, an identifier NFKC folds to I")))

#: a nesting depth past the interpreter's recursion limit and well inside
#: what `json.loads` accepts, where a recursive walk of the parsed value
#: fails
_PAST = sys.getrecursionlimit() + 50

#: what `json.loads` accepts
JSON = TextLanguage(
    "json", level="predicate", accepts=_is_json, generate=_generate_json,
    pool=string.printable, outside_pool="{'",
    extra_hazards=(HazardValue("text", "1e309", "a number past the largest double, which loads as inf"),
                   HazardValue("text", "NaN", "the non-standard NaN literal loads accepts"),
                   HazardValue("text", "\"\\ud800\"", "an escaped lone surrogate"),
                   HazardValue("text", "[" * 50 + "]" * 50, "fifty nested arrays"),
                   HazardValue("length", "[" * _PAST + "]" * _PAST,
                               f"arrays nested {_PAST} deep, past the recursion limit, which "
                               "loads accepts"),
                   HazardValue("length", '{"a":' * _PAST + "0" + "}" * _PAST,
                               f"objects nested {_PAST} deep, past the recursion limit, which "
                               "loads accepts")))

#: what `uuid.UUID` accepts: hyphenated, bare, braced and urn forms
UUID = TextLanguage(
    "uuid", level="predicate", accepts=_is_uuid, generate=_generate_uuid,
    pool="0123456789abcdef-", outside_pool="g ",
    extra_hazards=(HazardValue("text", "{12345678-1234-5678-1234-567812345678}", "a braced uuid"),
                   HazardValue("text", "urn:uuid:12345678-1234-5678-1234-567812345678", "a urn uuid"),
                   HazardValue("text", "12345678123456781234567812345678", "a uuid with no hyphens"),
                   HazardValue("text", "12345678-1234-5678-1234-567812345678".upper(), "an upper-case uuid")))

def _accepted(accepts: Callable[[str], bool],
              hazards: tuple[HazardValue, ...]) -> tuple[HazardValue, ...]:
    """Intent:
        The hazards whose text `accepts` takes on the running Python, so a parser's other
        spellings are hazards only where that parser reads them.
    """
    return tuple(h for h in hazards if isinstance(h.value, str) and accepts(h.value))


#: what `date.fromisoformat` accepts on the running Python
ISO_DATE = TextLanguage(
    "iso_date", level="predicate", accepts=_is_iso_date,
    generate=_generate_iso_date, pool="0123456789-", outside_pool="/ a",
    extra_hazards=_accepted(_is_iso_date, (
        HazardValue("time", "0001-01-01", "the first date"),
        HazardValue("time", "9999-12-31", "the last date"),
        HazardValue("time", "2000-02-29", "a leap day"),
        HazardValue("time", "20260928", "a basic-format date, no hyphens"),
        HazardValue("time", "2026-W39-1", "a week date"),
        HazardValue("time", "2026W391", "a basic-format week date"))))

#: what `datetime.fromisoformat` accepts on the running Python
ISO_DATETIME = TextLanguage(
    "iso_datetime", level="predicate", accepts=_is_iso_datetime,
    generate=_generate_iso_datetime, pool="0123456789-T:.+", outside_pool="/ a",
    extra_hazards=_accepted(_is_iso_datetime, (
        HazardValue("time", "1970-01-01T00:00:00+00:00", "the epoch, aware"),
        HazardValue("time", "1970-01-01T00:00:00", "the epoch, naive"),
        HazardValue("time", "2021-03-28T02:30:00", "inside a daylight-saving gap in Europe"),
        HazardValue("time", "2021-10-31T02:30:00", "inside a daylight-saving fold in Europe"),
        HazardValue("time", "9999-12-31T23:59:59.999999", "the last microsecond"),
        HazardValue("time", "2026-09-28T12:00:00Z", "a Z offset"),
        HazardValue("time", "2026-09-28 12:00:00", "a space between date and time"),
        HazardValue("time", "20260928T120000", "a basic-format datetime"),
        HazardValue("time", "2026-09-28", "a date with no time"),
        HazardValue("time", "2026-09-28T12:00:00,5", "a comma before the fraction"))))

#: what `ipaddress.IPv4Address` accepts
IPV4 = TextLanguage(
    "ipv4", level="predicate", accepts=_is_ipv4, generate=_generate_ipv4,
    pool="0123456789.", outside_pool=" a:",
    extra_hazards=(HazardValue("text", "0.0.0.0", "the unspecified address"),
                   HazardValue("text", "255.255.255.255", "the broadcast address"),
                   HazardValue("text", "127.0.0.1", "loopback")))

#: what `ipaddress.IPv6Address` accepts
IPV6 = TextLanguage(
    "ipv6", level="predicate", accepts=_is_ipv6, generate=_generate_ipv6,
    pool="0123456789abcdef:", outside_pool=" g.",
    extra_hazards=(HazardValue("text", "::", "the unspecified address"),
                   HazardValue("text", "::1", "loopback"),
                   HazardValue("text", "::ffff:192.0.2.128", "an IPv4-mapped address")))

#: what `base64.b64decode(validate=True)` accepts and encodes back to itself
BASE64 = TextLanguage(
    "base64", level="predicate", accepts=_is_base64, generate=_generate_base64,
    pool=string.ascii_letters + string.digits + "+/=", outside_pool=" -_!",
    extra_hazards=(HazardValue("text", "QQ==", "one byte, two padding characters"),
                   HazardValue("text", "QUE=", "two bytes, one padding character")))

#: what `bytes.fromhex` accepts
HEX = TextLanguage(
    "hex", level="predicate", accepts=_is_hex, generate=_generate_hex,
    pool="0123456789abcdefABCDEF", outside_pool="g-",
    extra_hazards=(HazardValue("text", "de ad be ef", "hex with spaces between bytes"),
                   HazardValue("text", "DEADBEEF", "upper-case hex")))

#: lower-case words of letters and digits joined by single hyphens
SLUG = TextLanguage(
    "slug", level="regular", accepts=_is_slug, generate=_generate_slug,
    pool=string.ascii_lowercase + string.digits + "-", outside_pool=" _A.",
    schema={"pattern": "^" + _SLUG.pattern + "$"},
    extra_hazards=(HazardValue("text", "a", "one character"),
                   HazardValue("text", "a-" * 200 + "a", "many hyphenated words")))

#: the strings `shlex.quote` leaves alone: a non-empty word over the
#: characters a shell reads literally
SHELL_SAFE = TextLanguage(
    "shell_safe", level="predicate", accepts=_is_shell_safe,
    generate=_generate_shell_safe, pool=_SHELL_SAFE_CHARS, outside_pool=" '\"$*",
    schema={"pattern": "^[A-Za-z0-9@%_\\-+=:,./]+$"})

__all__ = ["BASE64", "HEX", "IDENTIFIER", "IPV4", "IPV6", "ISO_DATE",
           "ISO_DATETIME", "JSON", "SHELL_SAFE", "SLUG", "UUID"]
