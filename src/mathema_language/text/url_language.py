# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""`L[url]`: absolute URL text with an authority, the way a program
receives a link, a redirect target or a webhook address, read as
`urllib.parse.urlsplit` reads it and admitted only where that reading
is the one every reader makes.

A member is text with no space or control character (no code point at
or below U+0020, which `urlsplit` would strip or drop) made of:

- a scheme: an ASCII letter, then ASCII letters, digits, `+`, `.`, `-`;
- `://`;
- optionally a user part ending in `@`: printable ASCII other than
  `/ ? # [ ] \\` (it may itself hold `:` and `@`; the host starts after
  the last `@`);
- a host: one or more ASCII letters, digits, `-` and `.`;
- optionally `:` and a port of one to five ASCII digits, at most 65535;
- optionally a `/`, `?` or `#` and any further text: the path, query and
  fragment.

So `urlsplit(text)` raises nothing, its `scheme` and `hostname` are the
written ones in lower case and its `port` the written number. Left out
on purpose of the definition: a host in brackets (an IPv6 literal), a
host outside ASCII, an empty port, and a backslash before the path,
which `urlsplit` and a browser read as different hosts.

Its hazards are the URLs code that checks a link gets wrong: a user part
that looks like a host, a port spelled with leading zeros, upper case in
the scheme and host, `..` and its percent-encoded spellings in the path,
and a second URL carried in the path or query.

The language is defined twice and tested equal: `contains` asks
`urlsplit`, and `URL_PATTERN`, read in full, is the same set as a
regular expression."""
from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import SplitResult, urlsplit

from .._surface import HazardValue
from ._kit import TextLanguage

_SCHEME = r"[A-Za-z][A-Za-z0-9+.\-]*"
#: the user part: printable ASCII other than `/ ? # [ \ ]`, then `@`
_USER = r"(?:[!\"$-.0->@-Z\^-~]*@)?"
_HOST = r"[A-Za-z0-9.\-]+"
#: one to five digits, at most 65535
_PORT = r"(?:[0-9]{1,4}|[0-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])"
#: a path, query and fragment: `/`, `?` or `#`, then text with no space or control character
_REST = r"(?:[/?#][^\x00-\x20]*)?"

#: the regular expression, read in full, of `L[url]`
URL_PATTERN = _SCHEME + "://" + _USER + _HOST + "(?::" + _PORT + ")?" + _REST

_SCHEME_RE = re.compile(_SCHEME)
_HOST_RE = re.compile(_HOST)
_PORT_RE = re.compile(r"[0-9]{1,5}")

_HAZARDS = (
    ("http://example.com", "no path at all"),
    ("http://example.com/", "the root path"),
    ("HTTP://EXAMPLE.COM/", "an upper-case scheme and host, read in lower case"),
    ("http://example.com:80/", "the scheme's own port, written out"),
    ("http://example.com:00080/", "a port with leading zeros"),
    ("http://example.com:0/", "port zero"),
    ("http://user:secret@example.com/", "a user and a password"),
    ("http://example.com@evil.example/", "a user part that looks like a host"),
    ("http://a@b@example.com/", "two at signs: the host follows the last"),
    ("http://example.com.evil.example/", "a host that starts with another host"),
    ("http://example.com./", "a host with a trailing dot"),
    ("http://127.0.0.1/", "a host that is an IPv4 address"),
    ("http://2130706433/", "a host that is one number"),
    ("http://example.com/a/../b", "a '..' segment in the path"),
    ("http://example.com/a/%2e%2e/b", "a percent-encoded '..' segment"),
    ("http://example.com/a\\b", "a backslash in the path, a slash to a browser"),
    ("http://example.com//evil.example/", "a doubled slash at the start of the path"),
    ("http://example.com/?next=http://evil.example/", "a second URL in the query"),
    ("http://example.com/#@evil.example", "an at sign in the fragment"),
    ("http://example.com?a", "a query with no path"),
    ("http://example.com/caf\u00e9", "a path outside ASCII"),
    ("javascript://example.com/%0aalert(1)", "a scheme that runs code"),
    ("file://localhost/etc/passwd", "a local file"),
    ("x://h", "the shortest member"),
)

_OUTSIDE = (
    "", "example.com", "//example.com/", "/path", "http:/example.com", "http://", "http:///path",
    "http://example.com:", "http://example.com:65536/", "http://example.com:8o/", "http://exa mple.com/",
    "http://example.com/a b", "http://example.com/\n", " http://example.com/", "http://[::1]/",
    "http://example.com\\@evil.example/", "http://ex\u00e4mple.com/", "1http://example.com/",
    "http://user@/", "mailto:user@example.com",
)


def url_parts(text: object) -> SplitResult | None:
    """Intent:
        The parts `urlsplit` reads from `text` when `text` is in `L[url]`, else None.

    Notes:
        A member has no code point at or below U+0020; a scheme of an ASCII letter then ASCII
        letters, digits, `+`, `.`, `-`; `://`; an authority of printable ASCII with no bracket or
        backslash, whose host, after the last `@` and before any `:`, is one or more letters,
        digits, `-` and `.`; and a port, when a `:` follows the host, of one to five digits that
        `urlsplit` reads (at most 65535).
    """
    if not isinstance(text, str) or any(ord(c) <= 0x20 for c in text):
        return None
    scheme, mark, _ = text.partition("://")
    if not mark or _SCHEME_RE.fullmatch(scheme) is None:
        return None
    try:
        parts = urlsplit(text)
        parts.port  # noqa: B018
    except ValueError:
        return None
    netloc = parts.netloc
    printable = all(0x21 <= ord(c) <= 0x7E for c in netloc)
    if parts.scheme != scheme.lower() or not printable or set(netloc) & set("[]\\"):
        return None
    host, colon, port = netloc.rpartition("@")[2].partition(":")
    if _HOST_RE.fullmatch(host) is None or parts.hostname != host.lower():
        return None
    if colon and _PORT_RE.fullmatch(port) is None:
        return None
    return parts


def _is_url(text: str) -> bool:
    """Intent:
        Whether `text` is in `L[url]`.
    """
    return url_parts(text) is not None


_SEGMENTS = ("a", "api", "v1", "index.html", "a%20b", "caf\u00e9", "~user", "x;y=1", "-", "_")


def _generate_url(rng: random.Random) -> str:
    """Intent:
        A random member: a common or made-up scheme, sometimes a user part, a host of one to
        three labels or an IPv4 address, sometimes a port, and up to three path segments, a
        query and a fragment.
    """
    scheme = rng.choice(["http", "https", "HTTPS", "ftp", "ws", "git+ssh", "x"])
    user = rng.choice(["", "", "", "user@", "user:pw@", "a@b@"])
    labels = [rng.choice(["example", "www", "api", "localhost", "a-b", "x1", "COM", "test"])
              for _ in range(rng.randint(1, 3))]
    host = rng.choice([".".join(labels), ".".join(labels), "127.0.0.1", "10.0.0.1"])
    port = rng.choice(["", "", ":80", ":443", ":8080", ":0", ":65535", ":00080"])
    path = "".join("/" + rng.choice(_SEGMENTS) for _ in range(rng.randint(0, 3)))
    path += rng.choice(["", "", "/"])
    query = rng.choice(["", "", "?q=1", "?a=1&b=2", "?"])
    fragment = rng.choice(["", "", "#top", "#"])
    return scheme + "://" + user + host + port + path + query + fragment


@dataclass(frozen=True)
class UrlLanguage(TextLanguage):
    """`L[url]`, defined by `pattern`, read in full, and by `urlsplit`."""
    pattern: str = URL_PATTERN

    def definition(self) -> dict[str, Any]:
        """The regular-language term of this language: its pattern,
        read in full."""
        from . import _regular
        return _regular.term(self.pattern, 0, "matches")

    def to_json(self) -> dict[str, Any]:
        return {**super().to_json(), "definition": self.definition()}

    def outside(self, rng: random.Random) -> Any:
        return rng.choice([text for text in _OUTSIDE if not self.contains(text)])


URL = UrlLanguage(
    "url", level="regular", accepts=_is_url, generate=_generate_url,
    pool="abcxyz019:/.?#@%-_", outside_pool=" \n\\[", simplest="a",
    extra_hazards=tuple(HazardValue("text", text, note) for text, note in _HAZARDS))

__all__ = ["URL", "URL_PATTERN", "UrlLanguage", "url_parts"]
