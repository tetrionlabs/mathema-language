# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The alphabet languages: every string over a set of characters, the
empty string included, each with Python's own reading of the alphabet
as its membership test. The hazard sub-alphabets at the end are the
character classes real code mishandles, as languages of their own so a
claim can quantify over exactly them.
"""
from __future__ import annotations

import string
import unicodedata

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
    return True


def _is_ascii(c: str) -> bool:
    return ord(c) < 0x80


def _is_latin1(c: str) -> bool:
    return ord(c) < 0x100


def _is_printable(c: str) -> bool:
    return c.isprintable()


def _is_digit(c: str) -> bool:
    return c in string.digits


def _is_alpha(c: str) -> bool:
    return c.isalpha()


def _is_alnum(c: str) -> bool:
    return c.isalnum()


def _is_c0(c: str) -> bool:
    return ord(c) <= 0x20


def _is_format(c: str) -> bool:
    return unicodedata.category(c) == "Cf"


def _is_combining(c: str) -> bool:
    return unicodedata.category(c) in _MARK_CATEGORIES


def _is_surrogate(c: str) -> bool:
    return unicodedata.category(c) == "Cs"


def _folds_under_nfkc(c: str) -> bool:
    return unicodedata.normalize("NFKC", c) != c


def _is_non_bmp(c: str) -> bool:
    return ord(c) > 0xFFFF


#: every `str`, lone surrogates included: the carrier of text
UNICODE = TextLanguage(
    "unicode", accepts=_every_str, pool=_UNICODE_POOL,
    categories=_EVERY_ASSIGNED, planes=(0, 0, 0, 1, 2, 14, 15, 16))

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

__all__ = ["ALNUM", "ALPHA", "ASCII", "ASTRAL", "COMBINING", "COMPATIBILITY", "CONTROL",
           "DIGIT", "INVISIBLE", "LATIN1", "PRINTABLE", "SURROGATE", "UNICODE",
           "UNICODE_ALNUM", "UNICODE_ALPHA"]
