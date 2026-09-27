# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Text operations for claims, bound with `let`:

    let n = mathema_language.vocabulary.text.nfc, for text in L[unicode], f(n(text)) == f(text)

Each is a plain module-level function with a neutral id in
`__mathema_vocabulary__` (`text.nfc@1`), the name another runtime's
adaptor maps to its own implementation; the major number moves only
when the meaning does. Lengths count Unicode scalar values.
"""
from __future__ import annotations

import unicodedata


def nfc(text: str) -> str:
    """The canonical composed form."""
    return unicodedata.normalize("NFC", text)


def nfd(text: str) -> str:
    """The canonical decomposed form."""
    return unicodedata.normalize("NFD", text)


def nfkc(text: str) -> str:
    """The compatibility composed form: ligatures, fullwidth forms and
    superscripts folded onto their plain equivalents."""
    return unicodedata.normalize("NFKC", text)


def nfkd(text: str) -> str:
    """The compatibility decomposed form."""
    return unicodedata.normalize("NFKD", text)


def casefold(text: str) -> str:
    """Case removed for comparison, the full Unicode folding."""
    return text.casefold()


def lower(text: str) -> str:
    """Lower case, the full Unicode mapping."""
    return text.lower()


def upper(text: str) -> str:
    """Upper case, the full Unicode mapping."""
    return text.upper()


def count(text: str, part: str) -> int:
    """How many non-overlapping times `part` occurs in `text`."""
    return text.count(part)


def startswith(text: str, prefix: str) -> bool:
    """Whether `text` begins with `prefix`."""
    return text.startswith(prefix)


def endswith(text: str, suffix: str) -> bool:
    """Whether `text` ends with `suffix`."""
    return text.endswith(suffix)


def strip(text: str) -> str:
    """Leading and trailing whitespace removed."""
    return text.strip()


def splitlines(text: str) -> list[str]:
    """The lines of `text`, on every Unicode line boundary."""
    return text.splitlines()


def nfc_len(text: str) -> int:
    """The length in NFC code points, what a character-count truncator
    ought to count."""
    return len(unicodedata.normalize("NFC", text))


def utf8_len(text: str) -> int:
    """The length of `text` in UTF-8 bytes, what a byte-limited field
    counts."""
    return len(text.encode("utf-8", "surrogatepass"))


VOCABULARY: dict[str, object] = {
    "nfc": nfc, "nfd": nfd, "nfkc": nfkc, "nfkd": nfkd,
    "casefold": casefold, "lower": lower, "upper": upper,
    "count": count, "startswith": startswith, "endswith": endswith,
    "strip": strip, "splitlines": splitlines, "nfc_len": nfc_len,
    "utf8_len": utf8_len,
}

for _name, _fn in VOCABULARY.items():
    _fn.__mathema_vocabulary__ = f"text.{_name}@1"  # type: ignore[attr-defined]

__all__ = ["VOCABULARY", "casefold", "count", "endswith", "lower", "nfc",
           "nfc_len", "nfd", "nfkc", "nfkd", "splitlines", "startswith",
           "strip", "upper", "utf8_len"]
