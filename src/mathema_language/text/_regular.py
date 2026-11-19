# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A Python regular expression under a predicate, as a regular-language term.

A pattern, its flags and a predicate are a text language: `matches` holds
the strings `re.fullmatch` matches, `contains` those `re.search` finds it
in, `starts with` those `re.match` matches, `ends with` those it matches
from some position to the end. The term is that language written in a
small algebra with no dialect left in it: literal text, character sets,
concatenation, union, intersection, complement and bounded or unbounded
repetition, over every Python character. `term(pattern, flags,
predicate)` builds it as plain JSON data, `member(term, text)` decides
membership by Brzozowski derivatives, and neither needs a solver.

The translation runs in three steps.

1. Every one-character item (a literal, `.`, a class, a category) is the
   set of code points it matches, found by running `re` itself over every
   code point, so `\\d`, `\\w`, `\\s` and IGNORECASE are `re`'s own reading
   for the running Python's Unicode tables. A set is a tuple of disjoint,
   sorted, inclusive intervals.
2. A zero-width assertion (`^`, `$`, `\\A`, `\\Z`, `\\b`, `\\B`) holds or
   fails by the text around its position, so a sub-pattern reads as a list
   of pieces `(left, body, right)`: it matches a string in `body` wherever
   the text before the match meets `left` and the text after meets
   `right`. A context is `(empty, chars, only)`: the text there may be
   empty (when `empty`), or its adjacent character is in `chars`, and with
   `only` that character is the whole of it. Contexts are closed under
   conjunction, and joining two pieces turns the second's left context
   into a condition on the first's last character (or, when the first
   matched nothing, into a condition on the text before both), and the
   first's right context into a condition on the second's first
   character, likewise.
3. The predicate reads the pieces against the whole string: `matches`
   takes the pieces whose contexts admit empty text on both sides,
   `starts with` puts the right context's text after the body, `ends with`
   the left context's text before it, `contains` both around it.

Without backreferences, lookaround, conditionals, atomic groups and
possessive repeats, `re` backtracks through every way a pattern can match
from a position and tries every position, so a match exists exactly when
the string is in this language. With one of them the language is not
regular in general, and the term states a pair instead: `at_least`, read
with each assertion dropped, a backreference read as its group's language,
a conditional as both branches and an atomic group or possessive repeat
as the plain one, holds every member; `at_most` is the empty language.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from typing import Any

#: the version of the term's schema
TERM_VERSION = 1

#: the predicate words and the `re` reading each names
PREDICATES = {"matches": "fullmatch", "contains": "search", "starts with": "match",
              "ends with": "ends"}

#: the flags a term's source names, by word
FLAG_WORDS = {re.IGNORECASE: "ignore case", re.MULTILINE: "multiline", re.DOTALL: "dotall",
              re.ASCII: "ascii", re.VERBOSE: "verbose"}


class NotRegular(ValueError):
    """A pattern the translation does not read, or reads only as a bound, named."""


#: the last code point
_MAX_CODE = 0x10FFFF

#: every code point
_FULL: tuple[tuple[int, int], ...] = ((0, _MAX_CODE),)

#: the empty set
_NONE: tuple[tuple[int, int], ...] = ()

#: whether `\B` matches in the empty string, which differs between Pythons
_B_IN_EMPTY = re.search(r"\B", "") is not None


def _cs_union(*sets: Any) -> tuple[tuple[int, int], ...]:
    """Intent:
        Returns the union of interval sets, as sorted disjoint intervals with no two adjacent.
    """
    spans = sorted(span for s in sets for span in s)
    out: list[list[int]] = []
    for lo, hi in spans:
        if out and lo <= out[-1][1] + 1:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return tuple((lo, hi) for lo, hi in out)


def _cs_complement(s: Any) -> tuple[tuple[int, int], ...]:
    """Intent:
        Returns the code points not in `s`.
    """
    out, at = [], 0
    for lo, hi in s:
        if lo > at:
            out.append((at, lo - 1))
        at = hi + 1
    if at <= _MAX_CODE:
        out.append((at, _MAX_CODE))
    return tuple(out)


def _cs_inter(a: Any, b: Any) -> tuple[tuple[int, int], ...]:
    """Intent:
        Returns the code points in both `a` and `b`.
    """
    return _cs_complement(_cs_union(_cs_complement(a), _cs_complement(b)))


def _cs_has(s: Any, code: int) -> bool:
    return any(lo <= code <= hi for lo, hi in s)


def _sre() -> tuple[Any, Any, Any]:
    """Intent:
        Returns the regex parser, compiler and constants modules of the running Python.
    """
    import sys
    if sys.version_info >= (3, 11):
        from re import _compiler, _constants, _parser  # type: ignore[attr-defined]
        return _parser, _compiler, _constants
    import sre_compile
    import sre_constants
    import sre_parse
    return sre_parse, sre_compile, sre_constants


_EVERY_CODE_POINT: list[str] = []


def _every_code_point() -> str:
    """Intent:
        Returns the string of every code point in order, lone surrogates included.
    """
    if not _EVERY_CODE_POINT:
        _EVERY_CODE_POINT.append("".join(map(chr, range(_MAX_CODE + 1))))
    return _EVERY_CODE_POINT[0]


_ITEM_CHARS: dict[tuple[str, int], tuple[tuple[int, int], ...]] = {}


def _item_chars(op: Any, arg: Any, flags: int) -> tuple[tuple[int, int], ...]:
    """Intent:
        Returns the code points one parsed one-character item matches under `flags`: those `re`
        itself matches, found by running the item, repeated, over every code point.

    Notes:
        Such an item reads one character and nothing around it, so the runs of the repeated
        item over the string of every code point are the intervals of its set. A literal
        without IGNORECASE is its own code point.
    """
    parser, compiler, constants = _sre()
    if str(op) == "LITERAL" and not flags & re.IGNORECASE:
        return ((arg, arg),)
    key = (f"{op}:{arg!r}", flags & (re.IGNORECASE | re.ASCII | re.DOTALL | re.UNICODE))
    if key not in _ITEM_CHARS:
        state = (getattr(parser, "State", None) or parser.Pattern)()
        state.flags = flags
        item = parser.SubPattern(state, [(op, arg)])
        repeated = parser.SubPattern(state, [(constants.MAX_REPEAT,
                                              (1, constants.MAXREPEAT, item))])
        compiled = compiler.compile(repeated, flags)
        _ITEM_CHARS[key] = tuple((m.start(), m.end() - 1)
                                 for m in compiled.finditer(_every_code_point()))
    return _ITEM_CHARS[key]


def _class_chars(pattern: str, flags: int = 0) -> tuple[tuple[int, int], ...]:
    """Intent:
        Returns the code points a pattern of one one-character item (`\\d`, `[^a-z]`, `.`)
        matches under `flags`, as `re` reads it.

    Raises:
        NotRegular: the pattern is not one such item.
    """
    parser, _, _ = _sre()
    items = list(parser.parse(pattern, flags))
    if len(items) != 1 or str(items[0][0]) not in ("LITERAL", "NOT_LITERAL", "ANY", "IN", "CATEGORY"):
        raise NotRegular(f"the pattern {pattern!r}, which is not one character item")
    return _item_chars(items[0][0], items[0][1], parser.parse(pattern, flags).state.flags | flags)


# a regular expression, before z3: ("chars", set), ("eps",), ("empty",),
# ("cat", a, b, ...), ("alt", a, b, ...), ("loop", r, lo, hi or None),
# ("inter", a, b)
_EPS = ("eps",)
_EMPTY_RE = ("empty",)
_ANY_STAR = ("loop", ("chars", _FULL), 0, None)
_ANY_PLUS = ("loop", ("chars", _FULL), 1, None)


def _chars_re(s: Any) -> tuple:
    return ("chars", tuple(s)) if s else _EMPTY_RE


def _cat(*parts: tuple) -> tuple:
    flat: list[tuple] = []
    for p in parts:
        if p == _EMPTY_RE:
            return _EMPTY_RE
        if p == _EPS:
            continue
        flat.extend(p[1:] if p[0] == "cat" else [p])
    if not flat:
        return _EPS
    return flat[0] if len(flat) == 1 else ("cat", *flat)


def _alt(*parts: tuple) -> tuple:
    flat: list[tuple] = []
    for p in parts:
        for q in (p[1:] if p[0] == "alt" else [p]):
            if q != _EMPTY_RE and q not in flat:
                flat.append(q)
    if not flat:
        return _EMPTY_RE
    return flat[0] if len(flat) == 1 else ("alt", *flat)


def _inter(a: tuple, b: tuple) -> tuple:
    if _EMPTY_RE in (a, b):
        return _EMPTY_RE
    if b == _ANY_STAR:
        return a
    if a == _ANY_STAR:
        return b
    return ("inter", a, b)


def _loop(r: tuple, lo: int, hi: int | None) -> tuple:
    if hi == 0 or r == _EPS:
        return _EPS
    if r == _EMPTY_RE:
        return _EPS if lo == 0 else _EMPTY_RE
    if lo == hi == 1:
        return r
    return ("loop", r, lo, hi)


def _nullable(r: tuple) -> bool:
    """Intent:
        Returns whether the empty string is in `r`.
    """
    kind = r[0]
    if kind == "eps":
        return True
    if kind in ("chars", "empty"):
        return False
    if kind in ("cat", "inter"):
        return all(_nullable(p) for p in r[1:])
    if kind == "alt":
        return any(_nullable(p) for p in r[1:])
    if kind == "not":
        return not _nullable(r[1])
    return r[2] == 0 or _nullable(r[1])


def _nonempty(r: tuple) -> tuple:
    """Intent:
        Returns the non-empty strings of `r`, written without intersecting.

    Notes:
        A non-empty string of a concatenation has a first non-empty part, everything before it
        empty; one of a repeat of a nullable body is some iterations followed by a last
        non-empty one.
    """
    if not _nullable(r):
        return r
    kind = r[0]
    if kind in ("eps", "empty"):
        return _EMPTY_RE
    if kind == "cat":
        parts = r[1:]
        return _alt(*[_cat(_nonempty(parts[i]), *parts[i + 1:]) for i in range(len(parts))])
    if kind == "alt":
        return _alt(*[_nonempty(p) for p in r[1:]])
    if kind == "inter":
        return _inter(_nonempty(r[1]), r[2])
    sub, hi = r[1], r[3]
    if not _nullable(sub):
        return _loop(sub, 1, hi)
    return _cat(_loop(sub, 0, None if hi is None else hi - 1), _nonempty(sub))


def _edge(r: tuple, chars: Any, at_end: bool) -> tuple:
    """Intent:
        Returns the non-empty strings of `r` whose last character (first, when not `at_end`) is
        in `chars`, written without intersecting where `r` has no intersection of its own.
    """
    kind = r[0]
    if kind in ("eps", "empty"):
        return _EMPTY_RE
    if kind == "chars":
        return _chars_re(_cs_inter(r[1], chars))
    if kind == "alt":
        return _alt(*[_edge(p, chars, at_end) for p in r[1:]])
    if kind == "inter":
        return _inter(_edge(r[1], chars, at_end), r[2])
    if kind == "cat":
        parts = list(r[1:])
        order = range(len(parts) - 1, -1, -1) if at_end else range(len(parts))
        out = []
        for i in order:
            if at_end:
                out.append(_cat(*parts[:i], _edge(parts[i], chars, True)))
            else:
                out.append(_cat(_edge(parts[i], chars, False), *parts[i + 1:]))
            if not _nullable(parts[i]):
                break
        return _alt(*out)
    sub, lo, hi = r[1], r[2], r[3]
    rest = _loop(sub, 0 if _nullable(sub) else max(lo - 1, 0), None if hi is None else hi - 1)
    edge = _edge(sub, chars, at_end)
    return _cat(rest, edge) if at_end else _cat(edge, rest)


def _singles(r: tuple) -> tuple[tuple[int, int], ...]:
    """Intent:
        Returns the code points `c` for which the one-character string `c` is in `r`.
    """
    kind = r[0]
    if kind == "chars":
        return r[1]
    if kind in ("eps", "empty"):
        return _NONE
    if kind == "alt":
        return _cs_union(*[_singles(p) for p in r[1:]])
    if kind == "inter":
        return _cs_inter(_singles(r[1]), _singles(r[2]))
    if kind == "cat":
        parts = r[1:]
        return _cs_union(*[_singles(p) for i, p in enumerate(parts)
                           if all(_nullable(q) for j, q in enumerate(parts) if j != i)])
    sub, lo, hi = r[1], r[2], r[3]
    if (hi is None or hi >= 1) and (lo <= 1 or _nullable(sub)):
        return _singles(sub)
    return _NONE


def _re_sets(r: tuple, out: set) -> set:
    """Intent:
        Returns the character sets `r` names, added to `out`.
    """
    if r[0] == "chars":
        out.add(r[1])
    elif r[0] in ("cat", "alt", "inter"):
        for p in r[1:]:
            _re_sets(p, out)
    elif r[0] in ("loop", "not"):
        _re_sets(r[1], out)
    return out


# a context: (empty, chars, only); see the section comment
_TRIVIAL = (True, _FULL, False)
_AT_EDGE = (True, _NONE, False)


def _ctx_and(a: tuple, b: tuple) -> tuple:
    """Intent:
        Returns the context that holds exactly where both `a` and `b` hold.
    """
    return (a[0] and b[0], _cs_inter(a[1], b[1]), a[2] or b[2])


def _ctx_possible(c: tuple) -> bool:
    return c[0] or bool(c[1])


def _ctx_text(c: tuple, after: bool) -> tuple:
    """Intent:
        Returns the texts `c` admits on one side of a match: after it when `after`, else before.
    """
    empty, chars, only = c
    if c == _TRIVIAL:
        return _ANY_STAR
    edge = _chars_re(chars) if only else (
        _cat(_chars_re(chars), _ANY_STAR) if after else _cat(_ANY_STAR, _chars_re(chars)))
    return _alt(_EPS, edge) if empty else edge


def _ends_in(body: tuple, c: tuple, at_end: bool) -> tuple[tuple, bool]:
    """Intent:
        Returns the non-empty strings of `body` whose last character (first, when not `at_end`)
        meets context `c`, and whether `c` also requires the text beyond them to be empty.
    """
    empty, chars, only = c
    if only:
        return _chars_re(_cs_inter(_singles(body), chars)), True
    if chars == _FULL:
        return _nonempty(body), False
    return _edge(body, chars, at_end), False


def _join(a: list, b: list) -> list:
    """Intent:
        Returns the pieces of a sub-pattern followed by another, from the pieces of each.
    """
    out = []
    for l1, r1, c1 in a:
        for l2, r2, c2 in b:
            lefts = [(l1, r1)]
            if l2 != _TRIVIAL:
                lefts = []
                if _nullable(r1):
                    lefts.append((_ctx_and(l1, l2), _EPS))
                body, edge = _ends_in(r1, l2, at_end=True)
                lefts.append((_ctx_and(l1, _AT_EDGE) if edge else l1, body))
            rights = [(r2, c2)]
            if c1 != _TRIVIAL:
                rights = []
                if _nullable(r2):
                    rights.append((_EPS, _ctx_and(c1, c2)))
                body, edge = _ends_in(r2, c1, at_end=False)
                rights.append((body, _ctx_and(c2, _AT_EDGE) if edge else c2))
            for left, x in lefts:
                for y, right in rights:
                    out.append((left, _cat(x, y), right))
    return _merge(out)


def _merge(pieces: list) -> list:
    """Intent:
        Returns `pieces` with those of equal contexts joined into one and the impossible ones
        dropped.
    """
    by: dict[tuple, tuple] = {}
    for left, body, right in pieces:
        if body == _EMPTY_RE or not _ctx_possible(left) or not _ctx_possible(right):
            continue
        key = (left, right)
        by[key] = _alt(by[key], body) if key in by else body
    return [(left, body, right) for (left, right), body in by.items()]


def _power(pieces: list, n: int) -> list:
    out = [(_TRIVIAL, _EPS, _TRIVIAL)]
    for _ in range(n):
        out = _join(out, pieces)
    return out


#: the largest repeat count of a sub-pattern with assertions that is written out
_UNROLL = 32


class _Regex:
    """A Python regular expression as pieces. With `relax`, a construct that is not regular is
    read as a wider one and named in `not_exact`; without it, it raises `NotRegular`."""

    def __init__(self, pattern: Any, flags: int = 0, relax: bool = False) -> None:
        if isinstance(pattern, re.Pattern):
            pattern, flags = pattern.pattern, pattern.flags | flags
        if not isinstance(pattern, str):
            raise NotRegular(f"the pattern {pattern!r}, a bytes pattern")
        self.pattern = pattern
        self.relax = relax
        self.not_exact: list[str] = []
        self.groups: dict[int, list] = {}
        parser, _, _ = _sre()
        try:
            re.compile(pattern, flags)
            parsed = parser.parse(pattern, flags)
        except (re.error, ValueError, TypeError) as e:
            raise NotRegular(f"the pattern {pattern!r}, which does not compile ({e})") from e
        self.flags = parsed.state.flags | flags
        if self.flags & re.LOCALE:
            raise NotRegular(f"the pattern {pattern!r}, under the LOCALE flag")
        self.pieces = self._seq(list(parsed), self.flags)

    def _wider(self, what: str, pieces: list) -> list:
        """Intent:
            Returns `pieces`, a wider reading of a construct that is not regular, noting it.

        Raises:
            NotRegular: the translation is not relaxed.
        """
        if not self.relax:
            raise NotRegular(f"the pattern {self.pattern!r} ({what})")
        if what not in self.not_exact:
            self.not_exact.append(what)
        return pieces

    def _seq(self, items: Any, flags: int) -> list:
        out = [(_TRIVIAL, _EPS, _TRIVIAL)]
        for op, arg in items:
            out = _join(out, self._item(op, arg, flags))
        return out

    def _item(self, op: Any, arg: Any, flags: int) -> list:
        """Intent:
            Returns one parsed item as pieces.

        Raises:
            NotRegular: the item is a backreference, a lookaround, a conditional, an atomic
                group, a possessive repeat, or an assertion inside an unbounded repeat, and the
                translation is not relaxed.
        """
        name = str(op)
        _, _, constants = _sre()
        if name in ("LITERAL", "NOT_LITERAL", "ANY", "IN", "CATEGORY"):
            return [(_TRIVIAL, _chars_re(_item_chars(op, arg, flags)), _TRIVIAL)]
        if name in ("MAX_REPEAT", "MIN_REPEAT", "POSSESSIVE_REPEAT"):
            lo, hi, sub = arg
            body = self._seq(sub, flags)
            if name == "POSSESSIVE_REPEAT":
                self._wider("a possessive repeat, which gives nothing back", [])
            return self._repeat(body, lo, None if hi == constants.MAXREPEAT else hi)
        if name == "SUBPATTERN":
            group, add, remove = arg[0], arg[1], arg[2]
            pieces = self._seq(arg[-1], (flags | add) & ~remove)
            if group is not None:
                self.groups[group] = pieces
            return pieces
        if name == "BRANCH":
            return _merge([p for b in arg[1] for p in self._seq(b, flags)])
        if name == "AT":
            return self._at(str(arg), flags)
        if name == "ATOMIC_GROUP":
            return self._wider("an atomic group", self._seq(arg, flags))
        if name == "GROUPREF":
            group = self.groups.get(arg)
            body = _alt(*[r for _, r, _ in group]) if group else _ANY_STAR
            return self._wider("a backreference", [(_TRIVIAL, body, _TRIVIAL)])
        if name == "GROUPREF_EXISTS":
            _, yes, no = arg
            both = self._seq(yes, flags) + (self._seq(no, flags) if no else [(_TRIVIAL, _EPS, _TRIVIAL)])
            return self._wider("a conditional group", _merge(both))
        if name in ("ASSERT", "ASSERT_NOT"):
            what = "a lookahead" if arg[0] >= 0 else "a lookbehind"
            return self._wider(what, [(_TRIVIAL, _EPS, _TRIVIAL)])
        raise NotRegular(f"the pattern {self.pattern!r} ({name.lower()})")

    def _repeat(self, body: list, lo: int, hi: int | None) -> list:
        """Intent:
            Returns pieces for `body` repeated `lo` to `hi` times (`None`: unbounded).

        Notes:
            An iteration that matches nothing only adds conditions at one position, so an
            unbounded repeat reads as its non-empty iterations alone.
        """
        if len(body) == 1 and body[0][0] == _TRIVIAL and body[0][2] == _TRIVIAL:
            return [(_TRIVIAL, _loop(body[0][1], lo, hi), _TRIVIAL)]
        if lo > _UNROLL or (hi is not None and hi > _UNROLL):
            free = _alt(*[r for _, r, _ in body])
            return self._wider(f"an assertion inside a repeat of more than {_UNROLL}",
                               [(_TRIVIAL, _loop(free, lo, hi), _TRIVIAL)])
        head = _power(body, lo)
        if hi is not None:
            return _join(head, _power(_merge([*body, (_TRIVIAL, _EPS, _TRIVIAL)]), hi - lo))
        steps = _merge([(left, _nonempty(r), right) for left, r, right in body])
        if any(left != _TRIVIAL or right != _TRIVIAL for left, _, right in steps):
            free = _alt(*[r for _, r, _ in steps])
            steps = self._wider("an anchor or word boundary inside an unbounded repeat",
                                [(_TRIVIAL, free, _TRIVIAL)])
        return _join(head, [(_TRIVIAL, _loop(steps[0][1], 0, None) if steps else _EPS, _TRIVIAL)])

    def _at(self, name: str, flags: int) -> list:
        """Intent:
            Returns the pieces of a zero-width assertion, read as `re` reads it under `flags`.
        """
        newline = ((10, 10),)
        multiline = bool(flags & re.MULTILINE)
        if name == "AT_BEGINNING" and multiline:
            return [((True, newline, False), _EPS, _TRIVIAL)]
        if name in ("AT_BEGINNING", "AT_BEGINNING_STRING"):
            return [(_AT_EDGE, _EPS, _TRIVIAL)]
        if name == "AT_END":
            return [(_TRIVIAL, _EPS, (True, newline, not multiline))]
        if name == "AT_END_STRING":
            return [(_TRIVIAL, _EPS, _AT_EDGE)]
        if name in ("AT_BOUNDARY", "AT_NON_BOUNDARY"):
            parser, _, _ = _sre()
            word_item = list(parser.parse(r"\w", flags & re.ASCII))[0]
            word = _item_chars(*word_item, flags & ~re.IGNORECASE)
            other = _cs_complement(word)
            if name == "AT_BOUNDARY":
                return [((False, word, False), _EPS, (True, other, False)),
                        ((True, other, False), _EPS, (False, word, False))]
            pieces = [((False, word, False), _EPS, (False, word, False)),
                      ((False, other, False), _EPS, (True, other, False)),
                      (_AT_EDGE, _EPS, (False, other, False))]
            if _B_IN_EMPTY:
                pieces.append((_AT_EDGE, _EPS, _AT_EDGE))
            return pieces
        raise NotRegular(f"the pattern {self.pattern!r} ({name.lower()})")

    def language(self, mode: str) -> tuple:
        """Intent:
            Returns the whole strings in which the pattern finds a match under `mode`:
            `fullmatch`, `match`, `search`, or `ends` (a match running to the end).
        """
        if mode not in ("fullmatch", "match", "search", "ends"):
            raise ValueError(f"a mode is fullmatch, match, search or ends, not {mode!r}")
        parts = []
        for left, body, right in self.pieces:
            if mode in ("fullmatch", "match") and not left[0]:
                continue
            if mode in ("fullmatch", "ends") and not right[0]:
                continue
            before = _EPS if mode in ("fullmatch", "match") else _ctx_text(left, after=False)
            after = _EPS if mode in ("fullmatch", "ends") else _ctx_text(right, after=True)
            parts.append(_cat(before, body, after))
        return _alt(*parts)

    def sets(self) -> set:
        """Intent:
            Returns every character set the pieces name, in bodies and contexts.
        """
        out: set = set()
        for left, body, right in self.pieces:
            _re_sets(body, out)
            out.update({left[1], right[1]})
        return out


# -- the term as plain data ----------------------------------------------------

def to_node(r: tuple) -> dict:
    """Intent:
        Returns the expression `r` as a term node: one-character sets of one code point and
        runs of them as literal text.
    """
    kind = r[0]
    if kind == "eps":
        return {"op": "epsilon"}
    if kind == "empty":
        return {"op": "empty"}
    if kind == "chars":
        s = r[1]
        if len(s) == 1 and s[0][0] == s[0][1]:
            return {"op": "literal", "text": chr(s[0][0])}
        return {"op": "chars", "ranges": [[lo, hi] for lo, hi in s]}
    if kind == "cat":
        args: list[dict] = []
        for p in r[1:]:
            node = to_node(p)
            if node["op"] == "literal" and args and args[-1]["op"] == "literal":
                args[-1] = {"op": "literal", "text": args[-1]["text"] + node["text"]}
            else:
                args.append(node)
        return args[0] if len(args) == 1 else {"op": "concat", "args": args}
    if kind in ("alt", "inter"):
        return {"op": "union" if kind == "alt" else "inter", "args": [to_node(p) for p in r[1:]]}
    if kind == "not":
        return {"op": "complement", "arg": to_node(r[1])}
    return {"op": "repeat", "arg": to_node(r[1]), "min": r[2], "max": r[3]}


def from_node(node: dict) -> tuple:
    """Intent:
        Returns the expression a term node states.

    Raises:
        ValueError: the node is not one of the term's forms.
    """
    op = node.get("op")
    if op == "epsilon":
        return _EPS
    if op == "empty":
        return _EMPTY_RE
    if op == "literal":
        return _cat(*[("chars", ((ord(c), ord(c)),)) for c in node["text"]])
    if op == "chars":
        return _chars_re(_cs_union(*[((lo, hi),) for lo, hi in node["ranges"]]))
    if op == "concat":
        return _cat(*[from_node(a) for a in node["args"]])
    if op == "union":
        return _alt(*[from_node(a) for a in node["args"]])
    if op == "inter":
        out = from_node(node["args"][0])
        for a in node["args"][1:]:
            out = _inter(out, from_node(a))
        return out
    if op == "complement":
        return ("not", from_node(node["arg"]))
    if op == "repeat":
        return _loop(from_node(node["arg"]), int(node["min"]),
                     None if node["max"] is None else int(node["max"]))
    raise ValueError(f"not a term node: {node!r}")


def term(pattern: Any, flags: int = 0, predicate: str = "matches") -> dict:
    """Intent:
        Returns the term of the strings for which `predicate` holds of a Python pattern under
        `flags`: exact, or, for a construct that is not regular, an at-least and at-most pair.

    Raises:
        NotRegular: the pattern does not compile, is a bytes pattern, or uses LOCALE.
        ValueError: `predicate` is not one of `PREDICATES`.
    """
    if predicate not in PREDICATES:
        raise ValueError(f"a predicate is one of {sorted(PREDICATES)}, not {predicate!r}")
    regex = _Regex(pattern, int(flags), relax=True)
    language = to_node(regex.language(PREDICATES[predicate]))
    source_pattern = pattern.pattern if isinstance(pattern, re.Pattern) else pattern
    words = sorted(word for flag, word in FLAG_WORDS.items() if regex.flags & flag)
    doc: dict[str, Any] = {
        "kind": "regular_language", "version": TERM_VERSION, "alphabet": [[0, _MAX_CODE]],
        "exact": not regex.not_exact,
        "source": {"dialect": "python-re", "pattern": source_pattern, "flags": words,
                   "predicate": predicate, "python": sys.version.split()[0],
                   "unicode": unicodedata.unidata_version}}
    if regex.not_exact:
        doc["at_least"] = language
        doc["at_most"] = {"op": "empty"}
        doc["source"]["not_exact"] = list(regex.not_exact)
    else:
        doc["language"] = language
    return doc


# -- membership by derivatives -------------------------------------------------

_DERIVATIVES: dict[tuple[tuple, int], tuple] = {}


def _derivative(r: tuple, code: int) -> tuple:
    """Intent:
        Returns the strings `w` with the character `code` followed by `w` in `r`.
    """
    key = (r, code)
    if key in _DERIVATIVES:
        return _DERIVATIVES[key]
    kind = r[0]
    if kind in ("eps", "empty"):
        out = _EMPTY_RE
    elif kind == "chars":
        out = _EPS if _cs_has(r[1], code) else _EMPTY_RE
    elif kind == "cat":
        first, rest = r[1], _cat(*r[2:])
        out = _cat(_derivative(first, code), rest)
        if _nullable(first):
            out = _alt(out, _derivative(rest, code))
    elif kind == "alt":
        out = _alt(*[_derivative(p, code) for p in r[1:]])
    elif kind == "inter":
        out = _inter(_derivative(r[1], code), _derivative(r[2], code))
    elif kind == "not":
        out = ("not", _derivative(r[1], code))
    else:
        sub, lo, hi = r[1], r[2], r[3]
        rest = _loop(sub, max(lo - 1, 0), None if hi is None else hi - 1)
        out = _cat(_derivative(sub, code), rest)
    if len(_DERIVATIVES) > 200_000:
        _DERIVATIVES.clear()
    _DERIVATIVES[key] = out
    return out


def holds(r: tuple, text: str) -> bool:
    """Intent:
        Returns whether `text` is in the expression `r`.
    """
    for c in text:
        r = _derivative(r, ord(c))
        if r == _EMPTY_RE:
            return False
    return _nullable(r)


def member(doc: dict, text: str, bound: str = "language") -> bool:
    """Intent:
        Returns whether `text` is in a term's language, or in its `at_least` or `at_most` bound
        (an exact term's language is both).
    """
    return holds(from_node(doc["language"] if "language" in doc else doc[bound]), text)
