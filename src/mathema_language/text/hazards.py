# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The text hazard corpus: the strings real code mishandles.

Each entry carries its hazard kind, in mathema's own vocabulary:
`control` for control, format, combining and surrogate code points,
`encoding` for text at or past an alphabet boundary, `length` for
overlong and pathological inputs, `text` for ordinary-looking text a
parser tends to read wrongly. A language filters this corpus by
membership, so a probe over `L[ascii]` never sees a non-ascii entry and
a probe over `L[unicode]` sees them all.
"""
from __future__ import annotations

from .._surface import HazardValue

_C0_PREFIX = bytes(range(0x21)).decode("latin-1")

_ENTRIES: tuple[tuple[str, str, str], ...] = (
    # control, format, combining and surrogate code points
    ("control", "\x00", "NUL"),
    ("control", _C0_PREFIX, "every C0 control code point, then a space"),
    ("control", "\x1f", "unit separator"),
    ("control", "\x7f", "DEL"),
    ("control", "\x85", "NEL, the C1 next-line control"),
    ("control", "\ud800", "a lone high surrogate, which no codec can encode"),
    ("control", "\udfff", "a lone low surrogate"),
    ("control", "\ud800\udc00", "a surrogate pair written as two code points"),
    ("control", "\ufeff", "a byte-order mark"),
    ("control", "\ufffc", "the object replacement character"),
    ("control", "\ufffa", "an interlinear annotation anchor"),
    ("control", "\u206a", "inhibit symmetric swapping, a deprecated format character"),
    ("control", "\u202e", "a right-to-left override"),
    ("control", "\u200b", "a zero-width space"),
    ("control", "\u200d", "a zero-width joiner"),
    ("control", "\u2060", "a word joiner"),
    # text at or past an alphabet boundary, and text that changes under
    # normalisation or case mapping
    ("encoding", "\x80", "the first code point past 0x7f"),
    ("encoding", "\xff", "code point 0xff"),
    ("encoding", "\u0100", "the first code point past 0xff"),
    ("encoding", "ou\u0308ou\u0308ou\u0308ou\u0308", "combining diaereses, eight characters that render as four"),
    ("encoding", "-B\u030aB\u030a----8", "combining rings over letters"),
    ("encoding", "\u30d5\u309a", "a katakana letter with a combining semi-voiced mark"),
    ("encoding", "\u2100", "account of, which NFKC folds to a/c"),
    ("encoding", "\uff03", "a fullwidth number sign, which NFKC folds to #"),
    ("encoding", "\ufe13", "a presentation-form colon, which NFKC folds to :"),
    ("encoding", "\ufb01", "the fi ligature, one code point that upper-cases to two"),
    ("encoding", "\u00df", "sharp s, one code point that upper-cases to two"),
    ("encoding", "\u0130", "capital I with a dot, one code point that lower-cases to two"),
    ("encoding", "\u0390", "iota with dialytika and tonos, one code point that upper-cases to three"),
    ("encoding", "e\u0301", "e with a combining acute, two code points that NFC composes to one"),
    ("encoding", "\U0001f3f4\U000e0067\U000e0062\U000e0077\U000e006c\U000e0073\U000e007f",
     "a tag-sequence flag, seven code points rendering as one symbol"),
    ("encoding", "\U0001f468\u200d\U0001f469", "a zero-width-joiner emoji sequence"),
    ("encoding", "\U0001f4a9", "a non-BMP symbol"),
    ("encoding", "\U0001d120", "a non-BMP musical symbol"),
    ("encoding", "\U00101234", "a private-use code point in plane 16"),
    ("encoding", "\u0430" * 25, "twenty-five Cyrillic a, a homoglyph of the Latin letter"),
    ("encoding", "\u00a0", "a no-break space"),
    ("encoding", "\u202f", "a narrow no-break space"),
    ("encoding", "a\u060c b \u0623\u0648 c", "Latin and Arabic text mixed, with an Arabic comma"),
    # overlong and pathological inputs
    ("length", "<" * 51 + "a>" * 51, "unbalanced angle brackets that defeat a naive tag stripper"),
    ("length", ">" + "<a" * 501, "hundreds of opening tags"),
    ("length", "a" + "@a" * 5000 + "a", "an address-shaped string that makes a backtracking regex crawl"),
    ("length", "(" * 10000 + ":" + ")" * 10000, "deep nesting"),
    ("length", "[" * 10000 + "1" + "]" * 10000, "deeply nested brackets"),
    ("length", "x" * 65536, "sixty-four kibibytes of one character"),
    # ordinary-looking text a parser reads wrongly
    ("text", "&amp;amp;amp;", "a triply escaped ampersand"),
    ("text", "&foo&#x3b;", "an entity beside a numeric reference"),
    ("text", "&#xffffffff;", "a numeric character reference past the last code point"),
    ("text", "&#x110000;", "a numeric character reference one past the last code point"),
    ("text", "../../../etc/passwd", "a path that climbs out of its directory"),
    ("text", "\\\\example.com", "a UNC-style host"),
    ("text", "http:///example.com", "an empty authority"),
    ("text", "javascript:alert(1)", "a scheme that is code"),
    ("text", "www.example.org ", "a host with a trailing space"),
    ("text", "abc\ndef\rghi\r\n", "three newline conventions in one string"),
    ("text", "NA", "text that spells a missing value"),
    ("text", "null", "text that spells a null"),
    ("text", "None", "text that spells Python's None"),
    ("text", "nan", "text that spells not-a-number"),
    ("text", "1e309", "a number past the largest double"),
    ("text", "0x1p-1074", "the smallest subnormal, written as a hex float"),
    ("text", "1_000", "an underscored number literal"),
    ("text", "\u00b2", "superscript two, a digit str.isdigit accepts and int refuses"),
    ("text", "\u01c6", "a digraph letter that NFKC splits into two"),
    ("text", "\u0149", "a letter with a preceding apostrophe, one code point that upper-cases to two"),
)

#: runs of one multi-byte character after a one-byte "a", so every
#: character boundary sits at an odd byte offset and a cut at 24, 64,
#: 255 or 256 bytes lands inside a character for at least one of them
_BYTE_RUNS: tuple[tuple[str, str, str], ...] = tuple(
    ("encoding", "a" + ch * n,
     f"'a' then {n} of U+{ord(ch):04X} ({len(ch.encode('utf-8'))} bytes each), "
     f"{1 + n * len(ch.encode('utf-8'))} bytes in all")
    for ch, sizes in (("\u00e9", (12, 32, 128)), ("\u65e5", (8, 22, 85)),
                      ("\U0001f600", (6, 16, 64)))
    for n in sizes)

#: the corpus, deduplicated by value in the order above
TEXT_HAZARDS: tuple[HazardValue, ...] = tuple(
    HazardValue(kind, value, note)
    for kind, value, note in (*_ENTRIES, *_BYTE_RUNS))

__all__ = ["TEXT_HAZARDS"]
