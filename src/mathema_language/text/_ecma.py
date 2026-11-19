# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""An ECMAScript regular expression as pieces of a regular-language term.

The pattern is parsed here, by the grammar of ECMA-262 (with its Annex B
leniencies when neither `u` nor `v` is set), and read as `_regular`
reads a Python pattern: one-character items as sets, assertions as
contexts on the text around a match, and the whole as the strings a
predicate holds of.

Where it parts from Python's `re`: `\\d` is `[0-9]` and `\\w` is
`[A-Za-z0-9_]` whatever the flags; `\\s` is the specification's list of
white space and line terminators; `.` excludes the four line terminators
(`\\n`, `\\r`, U+2028, U+2029) unless `s` is set; `$` is the end of the
string alone, or before a line terminator under `m`; there is no `\\A` or
`\\Z`. Without `u` or `v` a string is its UTF-16 code units and every item
reads one unit; with either, it is code points. Under `i`, two characters
match when their canonical forms are equal: the simple upper case without
`u` or `v`, simple case folding with. Under `y` a match starts at the
start of the string.

A backreference, a lookahead or lookbehind, a `\\p{...}` property escape
and a `v`-mode class with nested classes, set operations or strings are
read as bounds: the term is not exact, and names which."""
from __future__ import annotations

import re
from typing import Any

from ._regular import (
    _ANY_STAR,
    _AT_EDGE,
    _EPS,
    _FULL,
    _TRIVIAL,
    NotRegular,
    _boundary,
    _chars_re,
    _cs_complement,
    _cs_has,
    _cs_inter,
    _cs_union,
    _join,
    _merge,
    _Regex,
)

#: the flag letters and the word each is named by; `g` and `d` change no language
FLAG_WORDS = {"i": "ignore case", "m": "multi line", "s": "dot all", "u": "unicode",
              "v": "unicode sets", "y": "sticky", "g": "global", "d": "indices"}

_LINE_ENDS = ((0x0A, 0x0A), (0x0D, 0x0D), (0x2028, 0x2029))
_DIGIT = ((0x30, 0x39),)
_WORD = ((0x30, 0x39), (0x41, 0x5A), (0x5F, 0x5F), (0x61, 0x7A))
_SPACE = _cs_union(((0x09, 0x0D),), ((0x20, 0x20),), ((0xA0, 0xA0),), ((0x1680, 0x1680),),
                   ((0x2000, 0x200A),), ((0x2028, 0x2029),), ((0x202F, 0x202F),),
                   ((0x205F, 0x205F),), ((0x3000, 0x3000),), ((0xFEFF, 0xFEFF),))
_SYNTAX = set("^$\\.*+?()[]{}|/")
_CONTROL = {"t": 9, "n": 10, "v": 11, "f": 12, "r": 13}

#: simple case foldings that neither `str.casefold` nor `str.lower` gives
_SIMPLE_FOLDS = {0xFB05: 0xFB06, 0x1FD3: 0x0390, 0x1FE3: 0x03B0}

_CANON: dict[bool, tuple[dict[int, int], dict[int, list[int]]]] = {}


def _canon(unicode: bool) -> tuple[dict[int, int], dict[int, list[int]]]:
    """Intent:
        Returns the canonical form of every character that is not its own, and the characters
        of each canonical form, for matching under `i`.

    Notes:
        Without `u` or `v`, a code unit's canonical form is its upper case when that is one
        code unit and does not turn a non-ASCII unit into an ASCII one. With either, it is the
        character's simple case folding: its full folding when that is one character, else
        its lower case when that is one character.
    """
    if unicode not in _CANON:
        forward: dict[int, int] = {}
        for code in range(0x110000 if unicode else 0x10000):
            ch = chr(code)
            if unicode:
                folded = ch.casefold()
                if len(folded) != 1:
                    folded = ch.lower() if len(ch.lower()) == 1 else ch
                to = _SIMPLE_FOLDS.get(code, ord(folded))
            else:
                upper = ch.upper()
                to = ord(upper) if len(upper) == 1 and ord(upper) <= 0xFFFF else code
                if code >= 128 and to < 128:
                    to = code
            if to != code:
                forward[code] = to
        back: dict[int, list[int]] = {}
        for code, to in forward.items():
            back.setdefault(to, []).append(code)
        _CANON[unicode] = (forward, back)
    return _CANON[unicode]


def _fold_closure(s: Any, unicode: bool) -> tuple[tuple[int, int], ...]:
    """Intent:
        Returns every character whose canonical form is that of some character of `s`.
    """
    forward, back = _canon(unicode)
    forms = {to for code, to in forward.items() if _cs_has(s, code)}
    forms.update(to for to in back if _cs_has(s, to) and to not in forward)
    extra = set(forms)
    for to in forms:
        extra.update(back.get(to, ()))
    return _cs_union(s, *[((c, c),) for c in extra])


class Ecma(_Regex):
    """An ECMAScript pattern under its flag letters, as pieces."""

    def __init__(self, pattern: Any, flags: str = "") -> None:
        if not isinstance(pattern, str) or not isinstance(flags, str):
            raise NotRegular(f"the pattern {pattern!r} with flags {flags!r}, which are not text")
        if len(set(flags)) != len(flags) or set(flags) - set(FLAG_WORDS) or {"u", "v"} <= set(flags):
            raise NotRegular(f"the pattern {pattern!r}, whose flags {flags!r} do not compile")
        self.pattern = pattern
        self.flags_text = flags
        self.relax = True
        self.reading = "at_least"
        self.native = True
        self.version = None
        self.varies: list[str] = []
        self.not_exact: list[str] = []
        self.groups: dict[int, list] = {}
        self.unicode = "u" in flags or "v" in flags
        self.sets = "v" in flags
        self.top = _FULL if self.unicode else ((0, 0xFFFF),)
        if self.unicode:
            pattern = re.sub("[\ud800-\udbff][\udc00-\udfff]", lambda m: chr(
                0x10000 + ((ord(m[0][0]) - 0xD800) << 10) + ord(m[0][1]) - 0xDC00), pattern)
            self.src = [ord(c) for c in pattern]
        else:
            self.src = []
            for c in pattern:
                code = ord(c)
                if code > 0xFFFF:
                    code -= 0x10000
                    self.src += [0xD800 + (code >> 10), 0xDC00 + (code & 0x3FF)]
                else:
                    self.src.append(code)
        self.pos = 0
        self.group_count, self.named = self._count_groups()
        self.pieces = self._disjunction(frozenset(flags) & frozenset("ims"))
        if self.pos != len(self.src):
            raise self._bad("an unmatched )")

    # -- reading the source ---------------------------------------------------

    def _bad(self, why: str) -> NotRegular:
        return NotRegular(f"the pattern {self.pattern!r}, which does not compile ({why})")

    def _peek(self, ahead: int = 0) -> str:
        at = self.pos + ahead
        return chr(self.src[at]) if at < len(self.src) else ""

    def _take(self, text: str) -> bool:
        if [ord(c) for c in text] == self.src[self.pos:self.pos + len(text)]:
            self.pos += len(text)
            return True
        return False

    def _count_groups(self) -> tuple[int, bool]:
        """Intent:
            Returns the number of capturing groups in the source and whether any is named.
        """
        count, named, in_class, i = 0, False, False, 0
        text = "".join(chr(c) for c in self.src)
        while i < len(text):
            c = text[i]
            if c == "\\":
                i += 2
                continue
            if in_class:
                in_class = c != "]"
            elif c == "[":
                in_class = True
            elif c == "(":
                if text[i + 1:i + 2] != "?":
                    count += 1
                elif text[i + 1:i + 3] == "?<" and text[i + 3:i + 4] not in ("=", "!"):
                    count += 1
                    named = True
            i += 1
        return count, named

    # -- the grammar ------------------------------------------------------------

    def _disjunction(self, mods: frozenset) -> list:
        pieces = self._alternative(mods)
        while self._take("|"):
            pieces = pieces + self._alternative(mods)
        return _merge(pieces)

    def _alternative(self, mods: frozenset) -> list:
        out = [(_TRIVIAL, _EPS, _TRIVIAL)]
        while self.pos < len(self.src) and self._peek() not in "|)":
            out = _join(out, self._term(mods))
        return out

    def _term(self, mods: frozenset) -> list:
        """Intent:
            Returns the pieces of one assertion, or of one atom and its quantifier.
        """
        if self._take("^"):
            return [((True, _LINE_ENDS, False) if "m" in mods else _AT_EDGE, _EPS, _TRIVIAL)]
        if self._take("$"):
            return [(_TRIVIAL, _EPS, (True, _LINE_ENDS, False) if "m" in mods else _AT_EDGE)]
        if self._take("\\b") or self._take("\\B"):
            word = self._word(mods)
            negated = chr(self.src[self.pos - 1]) == "B"
            return _boundary(word, _cs_complement(word), negated, True)
        for opener, what in (("(?=", "a lookahead"), ("(?!", "a lookahead"),
                             ("(?<=", "a lookbehind"), ("(?<!", "a lookbehind")):
            if self._take(opener):
                self._disjunction(mods)
                if not self._take(")"):
                    raise self._bad("an unterminated group")
                if what == "a lookahead" and not self.unicode:
                    self._quantifier()
                return self._wider(what, [(_TRIVIAL, _EPS, _TRIVIAL)])
        pieces = self._atom(mods)
        bounds = self._quantifier()
        if bounds is None:
            return pieces
        return self._repeat(pieces, *bounds)

    def _quantifier(self) -> tuple[int, int | None] | None:
        """Intent:
            Reads a quantifier, if one is next: its least and greatest count (`None`: unbounded).
        """
        bounds: tuple[int, int | None] | None = None
        if self._take("*"):
            bounds = (0, None)
        elif self._take("+"):
            bounds = (1, None)
        elif self._take("?"):
            bounds = (0, 1)
        elif self._peek() == "{":
            rest = "".join(chr(c) for c in self.src[self.pos:self.pos + 40])
            m = re.match(r"\{(\d+)(,(\d*))?\}", rest, re.ASCII)
            if m is None:
                if self.unicode:
                    raise self._bad("an incomplete quantifier")
                return None
            self.pos += m.end()
            lo = int(m[1])
            hi = lo if m[2] is None else (int(m[3]) if m[3] else None)
            if hi is not None and hi < lo:
                raise self._bad("a quantifier's numbers out of order")
            bounds = (lo, hi)
        if bounds is not None:
            self._take("?")
        return bounds

    def _atom(self, mods: frozenset) -> list:
        c = self._peek()
        if c == "(":
            return self._group(mods)
        if c == "[":
            self.pos += 1
            return self._class(mods)
        if c == ".":
            self.pos += 1
            return self._set(self.top if "s" in mods else _cs_inter(
                self.top, _cs_complement(_LINE_ENDS)), frozenset())
        if c == "\\":
            self.pos += 1
            return self._escape(mods)
        if c in "*+?":
            raise self._bad("nothing to repeat")
        if c in "{}]":
            if self.unicode:
                raise self._bad(f"a lone {c}")
            if c == "{" and re.match(r"\{\d+(,\d*)?\}", "".join(
                    chr(x) for x in self.src[self.pos:self.pos + 40]), re.ASCII):
                raise self._bad("nothing to repeat")
        self.pos += 1
        return self._set(((ord(c), ord(c)),), mods)

    def _set(self, s: Any, mods: frozenset) -> list:
        """Intent:
            Returns the pieces of one character in `s`, widened to its case forms under `i`.
        """
        if "i" in mods:
            s = _fold_closure(s, self.unicode)
        return [(_TRIVIAL, _chars_re(_cs_inter(s, self.top)), _TRIVIAL)]

    def _word(self, mods: frozenset) -> tuple[tuple[int, int], ...]:
        """Intent:
            Returns the word characters: `[A-Za-z0-9_]`, and, under `i` with `u` or `v`, the
            characters whose canonical form is one of them.
        """
        if "i" in mods and self.unicode:
            return _fold_closure(_WORD, True)
        return _WORD

    def _group(self, mods: frozenset) -> list:
        self.pos += 1
        if self._take("?:"):
            pass
        elif self._take("?<"):
            end = self.src.index(ord(">"), self.pos) if ord(">") in self.src[self.pos:] else -1
            if end < 0 or end == self.pos:
                raise self._bad("a group name")
            self.pos = end + 1
        elif self._take("?"):
            rest = "".join(chr(c) for c in self.src[self.pos:self.pos + 10])
            m = re.match(r"([ims]*)(?:-([ims]*))?:", rest)
            if m is None or not (m[1] or m[2]) or len(set(m[1] + (m[2] or ""))) != len(
                    m[1] + (m[2] or "")):
                raise self._bad("a group's modifiers")
            self.pos += m.end()
            mods = (mods | frozenset(m[1])) - frozenset(m[2] or "")
        pieces = self._disjunction(mods)
        if not self._take(")"):
            raise self._bad("an unterminated group")
        return pieces

    def _escape(self, mods: frozenset) -> list:
        """Intent:
            Returns the pieces of the atom a backslash starts.
        """
        c = self._peek()
        if c == "":
            raise self._bad("a trailing backslash")
        if c.isascii() and c.isdigit() and c != "0":
            start = self.pos
            while self._peek().isascii() and self._peek().isdigit():
                self.pos += 1
            number = int("".join(chr(x) for x in self.src[start:self.pos]))
            if number <= self.group_count:
                return self._wider("a backreference", [(_TRIVIAL, _ANY_STAR, _TRIVIAL)])
            if self.unicode:
                raise self._bad("a reference to a group that is not there")
            self.pos = start
        if c == "k" and (self.unicode or self.named):
            self.pos += 1
            if not self._take("<") or ord(">") not in self.src[self.pos:]:
                raise self._bad("a group reference")
            self.pos = self.src.index(ord(">"), self.pos) + 1
            return self._wider("a backreference", [(_TRIVIAL, _ANY_STAR, _TRIVIAL)])
        found = self._class_escape(mods)
        if found == "property":
            return self._wider("a property escape", [(
                _TRIVIAL, _ANY_STAR if self.sets else _chars_re(self.top), _TRIVIAL)])
        if found is not None:
            return self._set(found, mods)
        code = self._char_escape(in_class=False)
        return self._set(((code, code),), mods)

    def _class_escape(self, mods: frozenset) -> Any:
        """Intent:
            Reads `d D w W s S` after a backslash as its set, a `p{...}` or `P{...}` property
            as the word `property`, and anything else as None, reading nothing.
        """
        c = self._peek()
        sets = {"d": _DIGIT, "w": self._word(mods), "s": _SPACE}
        if c in ("d", "w", "s"):
            self.pos += 1
            return sets[c]
        if c in ("D", "W", "S"):
            self.pos += 1
            return _cs_inter(self.top, _cs_complement(sets[c.lower()]))
        if c in ("p", "P") and self.unicode:
            if self._peek(1) != "{" or ord("}") not in self.src[self.pos:]:
                raise self._bad("a property escape")
            self.pos = self.src.index(ord("}"), self.pos) + 1
            return "property"
        return None

    def _hex(self, digits: int) -> int | None:
        text = "".join(chr(c) for c in self.src[self.pos:self.pos + digits])
        if len(text) == digits and re.fullmatch("[0-9a-fA-F]+", text):
            self.pos += digits
            return int(text, 16)
        return None

    def _char_escape(self, in_class: bool) -> int:
        """Intent:
            Returns the code point (or code unit) the escape after a backslash names.
        """
        c = self._peek()
        self.pos += 1
        if c in _CONTROL:
            return _CONTROL[c]
        if c == "b" and in_class:
            return 8
        if c == "-" and in_class and self.unicode:
            return ord("-")
        if c == "0" and not (self._peek().isascii() and self._peek().isdigit()):
            return 0
        if c == "c":
            letter = self._peek()
            if letter.isascii() and letter.isalpha():
                self.pos += 1
                return ord(letter) % 32
            if self.unicode:
                raise self._bad("a control escape")
            if in_class and (letter.isascii() and letter.isdigit() or letter == "_"):
                self.pos += 1
                return ord(letter) % 32
            self.pos -= 1
            return ord("\\")
        if c == "x":
            value = self._hex(2)
            if value is not None:
                return value
            if self.unicode:
                raise self._bad("a hexadecimal escape")
            return ord("x")
        if c == "u":
            if self.unicode and self._take("{"):
                end = self.src.index(ord("}"), self.pos) if ord("}") in self.src[self.pos:] else -1
                text = "".join(chr(x) for x in self.src[self.pos:max(end, self.pos)])
                if end < 0 or not re.fullmatch("[0-9a-fA-F]+", text) or int(text, 16) > 0x10FFFF:
                    raise self._bad("a code point escape")
                self.pos = end + 1
                return int(text, 16)
            value = self._hex(4)
            if value is None:
                if self.unicode:
                    raise self._bad("a unicode escape")
                return ord("u")
            if self.unicode and 0xD800 <= value <= 0xDBFF and self._peek() == "\\" \
                    and self._peek(1) == "u":
                mark = self.pos
                self.pos += 2
                low = self._hex(4)
                if low is not None and 0xDC00 <= low <= 0xDFFF:
                    return 0x10000 + ((value - 0xD800) << 10) + low - 0xDC00
                self.pos = mark
            return value
        if c.isascii() and c.isdigit():
            if self.unicode:
                raise self._bad("a decimal escape")
            if c in "89":
                return ord(c)
            value = int(c)
            for _ in range(2):
                d = self._peek()
                if d and d in "01234567" and value * 8 + int(d) <= 0o377:
                    value = value * 8 + int(d)
                    self.pos += 1
            return value
        if self.unicode and c not in _SYNTAX:
            raise self._bad(f"the escape \\{c}")
        if c == "k" and not self.unicode:
            return ord("k")
        return ord(c)

    def _class(self, mods: frozenset) -> list:
        """Intent:
            Returns the pieces of a character class, the opening bracket read.

        Notes:
            Under `i` a class holds every character with the canonical form of one it names,
            and a negated class every character outside that.
        """
        negate = self._take("^")
        if self.sets:
            opaque = self._class_set_extras()
            if opaque:
                return self._wider("a class set operation", [(_TRIVIAL, _ANY_STAR, _TRIVIAL)])
        s: tuple[tuple[int, int], ...] = ()
        property_seen = False
        while not self._take("]"):
            if self.pos >= len(self.src):
                raise self._bad("an unterminated class")
            low = self._class_atom(mods)
            if low == "property":
                property_seen = True
                continue
            if self._peek() == "-" and self._peek(1) not in ("]", ""):
                self.pos += 1
                high = self._class_atom(mods)
                if isinstance(low, int) and isinstance(high, int):
                    if high < low:
                        raise self._bad("a class range out of order")
                    s = _cs_union(s, ((low, high),))
                    continue
                if self.unicode:
                    raise self._bad("a class range ending in a set")
                if high == "property":
                    property_seen = True
                    high = ()
                s = _cs_union(s, ((ord("-"), ord("-")),),
                              *[((x, x),) if isinstance(x, int) else x for x in (low, high)])
                continue
            s = _cs_union(s, ((low, low),) if isinstance(low, int) else low)
        if property_seen:
            return self._wider("a property escape", [(_TRIVIAL, _chars_re(self.top), _TRIVIAL)])
        if "i" in mods:
            s = _fold_closure(s, self.unicode)
        if negate:
            s = _cs_complement(s)
        return [(_TRIVIAL, _chars_re(_cs_inter(s, self.top)), _TRIVIAL)]

    def _class_atom(self, mods: frozenset) -> Any:
        """Intent:
            Reads one member of a class: a code point, a set, or the word `property`.
        """
        if self._take("\\"):
            found = self._class_escape(mods)
            if found is not None:
                return found
            return self._char_escape(in_class=True)
        code = self.src[self.pos]
        if self.sets and chr(code) in "()[]{}/-|":
            raise self._bad(f"a lone {chr(code)} in a class")
        self.pos += 1
        return code

    def _class_set_extras(self) -> bool:
        """Intent:
            Returns whether the `v`-mode class starting here nests a class, uses `&&` or `--`,
            or holds a `\\q{...}` string; if so, reads past its closing bracket.
        """
        depth, i, extras = 1, self.pos, False
        while i < len(self.src) and depth:
            c = chr(self.src[i])
            if c == "\\":
                extras = extras or chr(self.src[i + 1]) == "q" if i + 1 < len(self.src) else extras
                i += 2
                continue
            if c == "[":
                depth += 1
                extras = True
            elif c == "]":
                depth -= 1
            elif c in "&-" and i + 1 < len(self.src) and chr(self.src[i + 1]) == c:
                extras = True
            i += 1
        if depth:
            raise self._bad("an unterminated class")
        if extras:
            self.pos = i
        return extras

    # -- the whole string -------------------------------------------------------

    def mode(self, predicate: str) -> str:
        """Intent:
            Returns the reading of the whole string a predicate names: under `y` a match starts
            at the start of the string, so `contains` reads as `starts with` and `ends with` as
            `matches`.
        """
        sticky = "y" in self.flags_text
        return {"matches": "fullmatch", "starts with": "match",
                "contains": "match" if sticky else "search",
                "ends with": "fullmatch" if sticky else "ends"}[predicate]

    def flag_words(self) -> list[str]:
        return sorted(FLAG_WORDS[c] for c in self.flags_text)
