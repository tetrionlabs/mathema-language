# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The regular-language definition each named format language states.

A format language decides membership by a whole-string test: its own
pattern (`L[slug]`) or a standard-library parser (`bytes.fromhex` for
`L[hex]`). Its definition is the regular-language term of the strings
that test accepts, written here as a pattern read in full and compiled
by the same compiler that reads any `re` pattern. Three kinds of answer:

- exact: the test's language is regular and the same on every supported
  Python, and the term is that language (`slug`, `hex`, `base64`,
  `ipv4`, `ipv6`, `shell_safe`);
- bounds: an `at_most` term holding only members and an `at_least` term
  holding every member, on every supported Python, with the reason the
  two differ under `source.not_exact` (`identifier`, whose characters
  follow the Unicode version; `iso_date` and `iso_datetime`, whose
  spellings follow the running Python's `fromisoformat`; `uuid`, whose
  parser also reads spellings `int(text, 16)` allows);
- none: the language is not regular, and the reason is stated under
  `no_definition` in the definition's place (`json`, `yaml`, `toml`:
  brackets nest to any depth).

`stated(language)` returns the keys a language adds to its persisted
form, found by the membership test the language carries.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import _algebra, _regular

_HEX_DIGIT = "[0-9A-Fa-f]"
#: the white space `bytes.fromhex` skips between bytes
_HEX_SPACE = r"[ \t\n\r\x0b\x0c]"
HEX_PATTERN = f"{_HEX_SPACE}*(?:{_HEX_DIGIT}{{2}}{_HEX_SPACE}*)*"

_B64 = "[A-Za-z0-9+/]"
#: whole groups of four, then a last group of one byte (its second
#: character carries two bits, the other four zero) or of two bytes (its
#: third character carries four bits, the other two zero)
BASE64_PATTERN = (f"(?:{_B64}{{4}})*"
                  f"(?:{_B64}[AQgw]==|{_B64}{{2}}[AEIMQUYcgkosw048]=)?")

_OCTET = "(?:0|[1-9][0-9]?|1[0-9]{2}|2[0-4][0-9]|25[0-5])"
IPV4_PATTERN = f"{_OCTET}(?:\\.{_OCTET}){{3}}"

SHELL_SAFE_PATTERN = "[A-Za-z0-9_@%+=:,./-]+"


def _ipv6_pattern() -> str:
    """Intent:
        The pattern of what `ipaddress.IPv6Address` reads: eight groups of one to four hex
        digits joined by colons, the last two groups optionally written as an IPv4 address;
        or the same with one `::` standing for one or more missing groups, so at most seven
        are written; then optionally `%` and a scope of one or more characters, none of them
        `%` or `/`.
    """
    group = f"{_HEX_DIGIT}{{1,4}}"
    forms = [f"(?:{group}:){{7}}{group}", f"(?:{group}:){{6}}{IPV4_PATTERN}"]
    for before in range(8):
        left = f"(?:{group}:){{{before - 1}}}{group}" if before else ""
        room = 7 - before
        after = []
        if room >= 1:
            after.append(f"(?:{group}:){{0,{room - 1}}}{group}")
        if room >= 2:
            after.append(f"(?:{group}:){{0,{room - 2}}}{IPV4_PATTERN}")
        right = f"(?:{'|'.join(after)})?" if after else ""
        forms.append(f"{left}::{right}")
    return f"(?:{'|'.join(forms)})(?:%[^%/]+)?"


IPV6_PATTERN = _ipv6_pattern()

_UUID_HEX = (f"(?:{_HEX_DIGIT}{{32}}|{_HEX_DIGIT}{{8}}-{_HEX_DIGIT}{{4}}-{_HEX_DIGIT}{{4}}"
             f"-{_HEX_DIGIT}{{4}}-{_HEX_DIGIT}{{12}})")
#: the spellings `uuid.UUID` documents: bare or hyphenated hex, in braces
#: or not, after `urn:uuid:` or not
UUID_AT_MOST = f"(?:urn:uuid:)?(?:\\{{{_UUID_HEX}\\}}|{_UUID_HEX})"
#: `uuid.UUID` removes text and reads 32 characters, so a member has at least 32
UUID_AT_LEAST = "(?s:.){32,}"

_YEAR = "(?:[0-9]{3}[1-9]|[0-9]{2}[1-9][0-9]|[0-9][1-9][0-9]{2}|[1-9][0-9]{3})"
#: a calendar date `YYYY-MM-DD` of the years 0001 to 9999, with no 29 February
_DATE = (f"{_YEAR}-(?:(?:0[13578]|1[02])-(?:0[1-9]|[12][0-9]|3[01])"
         "|(?:0[469]|11)-(?:0[1-9]|[12][0-9]|30)"
         "|02-(?:0[1-9]|1[0-9]|2[0-8]))")
ISO_DATE_AT_MOST = _DATE
_DATE_SHAPE = "[0-9]{4}-?(?:[0-9]{2}-?[0-9]{2}|W[0-9]{2}(?:-?[0-9])?)"
#: four digits, then a month and day or a week and optional weekday, hyphens optional; or
#: such a date cut short and followed by one character outside ASCII, which
#: `date.fromisoformat` reads on Python 3.11 and later where the text is ten bytes of UTF-8
#: (`20260928\u00e9` is 28 September 2026)
ISO_DATE_AT_LEAST = f"(?:{_DATE_SHAPE}|[0-9]{{4}}[0-9W-]{{3,5}}[^\\x00-\\x7f])"
_CLOCK = "(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:\\.[0-9]{6})?"
_OFFSET = "[+-](?:[01][0-9]|2[0-3]):[0-5][0-9]"
ISO_DATETIME_AT_MOST = f"{_DATE}(?:[T ]{_CLOCK}(?:{_OFFSET})?)?"
#: a date in any of its spellings, then anything
ISO_DATETIME_AT_LEAST = f"{_DATE_SHAPE}(?s:.)*"

_NESTS = ("the language is not regular: its brackets nest to any depth, which no "
          "regular-language term states")


def _exact(pattern: str, decided_by: str) -> dict[str, Any]:
    """Intent:
        The exact term of the strings `pattern` matches in full, recording the test the
        language decides membership by.

    Raises:
        ValueError: the pattern's term is not exact.
    """
    doc = _regular.term(pattern, 0, "matches")
    if not doc["exact"]:
        raise ValueError(f"the pattern {pattern!r} has no exact term")
    doc["source"]["decided_by"] = decided_by
    return doc


def _bounded(at_most: str, at_least: str, decided_by: str, reason: str) -> dict[str, Any]:
    """Intent:
        The term of a language between two patterns read in full: `at_most` holds only
        members and `at_least` every member, on every supported Python.
    """
    low, high = _regular.term(at_most, 0, "matches"), _regular.term(at_least, 0, "matches")
    if not (low["exact"] and high["exact"]):
        raise ValueError("a bound's pattern has no exact term")
    data = _regular.versions_data()
    return {"kind": "regular_language", "version": _algebra.TERM_VERSION,
            "alphabet": low["alphabet"], "exact": False,
            "at_least": high["language"], "at_most": low["language"],
            "source": {"dialect": "python", "versions": data["versions"],
                       "unicode": list(dict.fromkeys(data["unicode"].values())),
                       "decided_by": decided_by,
                       "at_most_pattern": at_most, "at_least_pattern": at_least,
                       "not_exact": [reason]}}


_IDENTIFIER: dict[str, Any] = {}


def identifier_characters() -> dict[str, Any]:
    """Intent:
        Returns, from the shipped data file, the characters `str.isidentifier` takes first
        (`start`) and after the first (`continue`) on each supported Python: for each set the
        code points every version holds (`common`), each version's own (`by_version`) and
        those any version holds (`any`), with the versions covered.
    """
    if not _IDENTIFIER:
        import json
        from pathlib import Path
        raw = json.loads(
            (Path(__file__).parent / "data" / "python_identifier_characters.json").read_text())
        for name, entry in raw["sets"].items():
            common = tuple((lo, hi) for lo, hi in entry["common"])
            by_version = {v: _algebra._cs_union(common, tuple((lo, hi) for lo, hi in extra))
                          for v, extra in entry["extra"].items()}
            _IDENTIFIER[name] = {"common": common, "by_version": by_version,
                                 "any": _algebra._cs_union(*by_version.values())}
        _IDENTIFIER["versions"] = raw["versions"]
    return _IDENTIFIER


def _identifier() -> dict[str, Any]:
    """Intent:
        The term of what `str.isidentifier` accepts: one character it takes first, then any
        number it takes after the first. Both sets follow the Unicode version, so `at_most`
        is over the characters every supported Python takes and `at_least` over those any
        takes together with the code points still unassigned.
    """
    data = _regular.versions_data()
    sets = identifier_characters()
    start, rest = sets["start"], sets["continue"]
    start_low, start_high = start["common"], _algebra._cs_union(start["any"], data["unassigned"])
    rest_low, rest_high = rest["common"], _algebra._cs_union(rest["any"], data["unassigned"])

    def node(first: Any, later: Any) -> dict[str, Any]:
        return _algebra.canonical({"op": "concat", "args": [
            {"op": "chars", "ranges": [[lo, hi] for lo, hi in first]},
            {"op": "repeat", "min": 0, "max": None,
             "arg": {"op": "chars", "ranges": [[lo, hi] for lo, hi in later]}}]})

    return {"kind": "regular_language", "version": _algebra.TERM_VERSION,
            "alphabet": [[0, 0x10FFFF]], "exact": False,
            "at_least": node(start_high, rest_high), "at_most": node(start_low, rest_low),
            "source": {"dialect": "python", "versions": sets["versions"],
                       "unicode": list(dict.fromkeys(data["unicode"].values())),
                       "decided_by": "str.isidentifier",
                       "not_exact": ["the characters of an identifier differ between Python "
                                     "versions"]}}


def _slug() -> dict[str, Any]:
    from .predicates import _SLUG
    doc = _regular.term(_SLUG.pattern, _SLUG.flags, "matches")
    doc["source"]["decided_by"] = "re.fullmatch"
    return doc


_PREDICATES = "mathema_language.text.predicates."

#: the definition of each membership test, by the test's qualified name
_DEFINITIONS: dict[str, Callable[[], dict[str, Any]]] = {
    _PREDICATES + "_is_slug": _slug,
    _PREDICATES + "_is_hex": lambda: _exact(HEX_PATTERN, "bytes.fromhex"),
    _PREDICATES + "_is_base64": lambda: _exact(
        BASE64_PATTERN, "base64.b64decode(validate=True), encoding back to the same text"),
    _PREDICATES + "_is_ipv4": lambda: _exact(IPV4_PATTERN, "ipaddress.IPv4Address"),
    _PREDICATES + "_is_ipv6": lambda: _exact(IPV6_PATTERN, "ipaddress.IPv6Address"),
    _PREDICATES + "_is_shell_safe": lambda: _exact(
        SHELL_SAFE_PATTERN, "shlex.quote leaving a non-empty text unchanged"),
    _PREDICATES + "_is_uuid": lambda: _bounded(
        UUID_AT_MOST, UUID_AT_LEAST, "uuid.UUID",
        "uuid.UUID removes `urn:`, `uuid:`, braces and hyphens wherever they stand and reads "
        "what is left with int(text, 16), which allows a sign, a 0x prefix, underscores, "
        "white space and digits outside ASCII"),
    _PREDICATES + "_is_iso_date": lambda: _bounded(
        ISO_DATE_AT_MOST, ISO_DATE_AT_LEAST, "datetime.date.fromisoformat",
        "the spellings date.fromisoformat reads differ between Python versions, and a 29 "
        "February is a member only in a leap year"),
    _PREDICATES + "_is_iso_datetime": lambda: _bounded(
        ISO_DATETIME_AT_MOST, ISO_DATETIME_AT_LEAST, "datetime.datetime.fromisoformat",
        "the spellings datetime.fromisoformat reads differ between Python versions, and a 29 "
        "February is a member only in a leap year"),
    "str.isidentifier": _identifier,
}

#: why a membership test has no regular-language definition, by its qualified name
_NOT_REGULAR: dict[str, str] = {
    _PREDICATES + "_is_json": _NESTS,
    "mathema_language.text.yaml_language._is_yaml": _NESTS,
    "mathema_language.text.toml_language._is_toml": _NESTS,
}

_BUILT: dict[str, dict[str, Any]] = {}


def _name_of(test: Any) -> str:
    module = getattr(test, "__module__", None)
    qualified = getattr(test, "__qualname__", "")
    return qualified if module in (None, "builtins") else f"{module}.{qualified}"


def stated(language: Any) -> dict[str, Any]:
    """Intent:
        The keys a format language adds to its persisted form: `definition`, the term of the
        strings its membership test accepts; or `no_definition`, the reason it has none; or
        nothing, for a test this module has no reading of.
    """
    name = _name_of(getattr(language, "accepts", None))
    if name in _NOT_REGULAR:
        return {"no_definition": _NOT_REGULAR[name]}
    if name not in _DEFINITIONS:
        return {}
    if name not in _BUILT:
        _BUILT[name] = _DEFINITIONS[name]()
    import copy
    return {"definition": copy.deepcopy(_BUILT[name])}


__all__ = ["stated"]
