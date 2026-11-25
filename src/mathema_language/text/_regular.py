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
membership by Brzozowski derivatives, and neither needs a solver. The
algebra itself (the nodes, their canonical form and hash, and
membership) is the module `_algebra`, whose names are also importable
from here; this module is the compiler from `re` patterns to it.

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

import functools
import json
import re
import sys
from pathlib import Path
from typing import Any

from ._algebra import (  # noqa: F401
    _ANY_PLUS,
    _ANY_STAR,
    _DERIVATIVES,
    _EMPTY_RE,
    _EPS,
    _EVERY_STRING,
    _FULL,
    _MAX_CODE,
    _NONE,
    _READ,
    TERM_VERSION,
    Expr,
    Node,
    Ranges,
    _alt,
    _cat,
    _chars_re,
    _code,
    _cs_complement,
    _cs_has,
    _cs_inter,
    _cs_union,
    _derivative,
    _inter,
    _loop,
    _meaning,
    _nullable,
    _ranges,
    _re_sets,
    _text,
    _to_node,
    canonical,
    canonical_text,
    code_points,
    code_units,
    every_string_over,
    from_node,
    holds,
    member,
    of_length,
    shortest,
    term_hash,
    to_node,
)

#: the predicate words and the `re` reading each names
PREDICATES = {"matches": "fullmatch", "contains": "search", "starts with": "match",
              "ends with": "ends"}

#: the flags a term's source names, by word
FLAG_WORDS = {re.IGNORECASE: "ignore case", re.MULTILINE: "multi line", re.DOTALL: "dot all",
              re.ASCII: "ascii only", re.VERBOSE: "verbose"}


class NotRegular(ValueError):
    """A pattern the translation does not read, or reads only as a bound, named."""


class OtherVersion(RuntimeError):
    """A language about one Python version, asked to check or draw on another."""


#: a context: whether the text there may be empty, its adjacent characters, and whether that
#: character is the whole of it
Context = tuple[bool, Ranges, bool]

#: a piece: the left context, the body, the right context
Piece = tuple[Context, Expr, Context]


#: whether `\B` matches in the empty string, which differs between Pythons
_B_IN_EMPTY = re.search(r"\B", "") is not None


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


def _nonempty(r: Expr) -> Expr:
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


def _edge(r: Expr, chars: Any, at_end: bool) -> Expr:
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


def _singles(r: Expr) -> tuple[tuple[int, int], ...]:
    """Intent:
        Returns the code points `c` for which the one-character string `c` is in `r`.
    """
    kind = r[0]
    if kind == "chars":
        held: Ranges = r[1]
        return held
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


# a context: (empty, chars, only); see the section comment
_TRIVIAL: Context = (True, _FULL, False)
_AT_EDGE: Context = (True, _NONE, False)


def _ctx_and(a: Context, b: Context) -> Context:
    """Intent:
        Returns the context that holds exactly where both `a` and `b` hold.
    """
    return (a[0] and b[0], _cs_inter(a[1], b[1]), a[2] or b[2])


def _ctx_possible(c: Context) -> bool:
    return c[0] or bool(c[1])


def _ctx_text(c: Context, after: bool) -> Expr:
    """Intent:
        Returns the texts `c` admits on one side of a match: after it when `after`, else before.
    """
    empty, chars, only = c
    if c == _TRIVIAL:
        return _ANY_STAR
    edge = _chars_re(chars) if only else (
        _cat(_chars_re(chars), _ANY_STAR) if after else _cat(_ANY_STAR, _chars_re(chars)))
    return _alt(_EPS, edge) if empty else edge


def _ends_in(body: Expr, c: Context, at_end: bool) -> tuple[Expr, bool]:
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


def _join(a: list[Piece], b: list[Piece]) -> list[Piece]:
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


def _merge(pieces: list[Piece]) -> list[Piece]:
    """Intent:
        Returns `pieces` with those of equal contexts joined into one and the impossible ones
        dropped.
    """
    by: dict[tuple[Context, Context], Expr] = {}
    for left, body, right in pieces:
        if body == _EMPTY_RE or not _ctx_possible(left) or not _ctx_possible(right):
            continue
        key = (left, right)
        by[key] = _alt(by[key], body) if key in by else body
    return [(left, body, right) for (left, right), body in by.items()]


#: the most nodes a counted repeat of a sub-pattern with assertions is written out to
_WRITTEN = 20_000


def _written(pieces: list[Piece]) -> int:
    """Intent:
        Returns the number of nodes and ranges the bodies of `pieces` take when written out as
        a tree.
    """
    sizes: dict[int, int] = {}

    def size(r: Expr) -> int:
        if id(r) not in sizes and r[0] == "chars":
            sizes[id(r)] = len(r[1])
        if id(r) not in sizes:
            sizes[id(r)] = 1 + sum(size(p) for p in r[1:] if isinstance(p, tuple) and p
                                   and isinstance(p[0], str))
        return sizes[id(r)]

    return sum(size(r) for _, r, _ in pieces)


def _power(pieces: list[Piece], n: int) -> list[Piece] | None:
    """Intent:
        Returns the pieces of `pieces` followed by itself `n` times in all, or None once they
        would take more than `_WRITTEN` nodes to write out.
    """
    out = [(_TRIVIAL, _EPS, _TRIVIAL)]
    for _ in range(n):
        out = _join(out, pieces)
        if _written(out) > _WRITTEN:
            return None
    return out


def _boundary(word: Any, other: Any, negated: bool, in_empty: bool) -> list[Piece]:
    """Intent:
        Returns the pieces of a word boundary between the sets `word` and `other` (an edge of
        the string counting as `other`), or, when `negated`, of its absence, which holds in the
        empty string only when `in_empty`.
    """
    if not negated:
        return [((False, word, False), _EPS, (True, other, False)),
                ((True, other, False), _EPS, (False, word, False))]
    pieces = [((False, word, False), _EPS, (False, word, False)),
              ((False, other, False), _EPS, (True, other, False)),
              (_AT_EDGE, _EPS, (False, other, False))]
    if in_empty:
        pieces.append((_AT_EDGE, _EPS, _AT_EDGE))
    return pieces


#: the largest repeat count of a sub-pattern with assertions that is written out
_UNROLL = 32


#: the Python this interpreter is, as the data file names versions
RUNNING = f"{sys.version_info[0]}.{sys.version_info[1]}"

_VERSIONS: dict[str, Any] = {}


def versions_data() -> dict[str, Any]:
    """Intent:
        Returns what each supported Python reads differently, from the shipped data file: the
        versions with their Unicode versions, each version-dependent class as the code points
        every version holds (`common`) and each version's own (`by_version`), the code points
        unassigned in the newest version, the code points whose case reading differs between
        versions, and the versions on which each engine reading holds.
    """
    if not _VERSIONS:
        import json
        from pathlib import Path
        raw = json.loads((Path(__file__).parent / "data" / "python_versions.json").read_text())

        def spans(ranges: Any) -> tuple[tuple[int, int], ...]:
            return tuple((lo, hi) for lo, hi in ranges)

        classes = {}
        for name, entry in raw["classes"].items():
            common = spans(entry["common"])
            by_version = {v: _cs_union(common, spans(extra)) for v, extra in entry["extra"].items()}
            classes[name] = {"common": common, "by_version": by_version,
                             "any": _cs_union(*by_version.values())}
        _VERSIONS.update(
            dialect=raw["dialect"], versions=[v["python"] for v in raw["versions"]],
            unicode={v["python"]: v["unicode"] for v in raw["versions"]}, classes=classes,
            unassigned=spans(raw["unassigned"]), case_varies=spans(raw["case_varies"]),
            engine=raw["engine"])
    return _VERSIONS


def class_bounds(name: str, version: str | None = None) -> tuple[Any, Any]:
    """Intent:
        Returns the code points a version-dependent class holds as a pair: for one `version`
        that version's set twice; for every supported version, the code points all of them
        hold, and those any of them holds together with every code point unassigned in the
        newest, which a later version may give to the class.

    Raises:
        ValueError: `version` is not a supported Python.
    """
    data = versions_data()
    entry = data["classes"][name]
    if version is None:
        return entry["common"], _cs_union(entry["any"], data["unassigned"])
    if version not in entry["by_version"]:
        raise ValueError(f"python {version} is not one of the supported versions "
                         f"{data['versions']}")
    return entry["by_version"][version], entry["by_version"][version]


def version_dependent_characters(text: str) -> list[dict[str, Any]]:
    """Intent:
        Returns, for each character of `text` that the supported Pythons read differently, what
        differs: the classes it is in on some versions only (with the versions on each side),
        whether its case reading differs between versions, and whether it is unassigned in the
        newest version.
    """
    data = versions_data()
    out = []
    for c in dict.fromkeys(text):
        code = ord(c)
        classes = {}
        for name, entry in data["classes"].items():
            inside = [v for v in data["versions"] if _cs_has(entry["by_version"][v], code)]
            if inside and len(inside) != len(data["versions"]):
                classes[name] = {"in": inside,
                                 "not_in": [v for v in data["versions"] if v not in inside]}
        case = _cs_has(data["case_varies"], code)
        unassigned = _cs_has(data["unassigned"], code)
        if classes or case or unassigned:
            out.append({"character": c, "code": code, "classes": classes, "case_varies": case,
                        "unassigned": unassigned})
    return out


_CATEGORY_CLASS = {"CATEGORY_DIGIT": ("decimal", False), "CATEGORY_NOT_DIGIT": ("decimal", True),
                   "CATEGORY_SPACE": ("space", False), "CATEGORY_NOT_SPACE": ("space", True),
                   "CATEGORY_WORD": ("word", False), "CATEGORY_NOT_WORD": ("word", True)}

_LOWERS_INTO: dict[str, Any] = {}


def _lowers_into(target: Any) -> tuple[tuple[int, int], ...]:
    """Intent:
        Returns the code points whose lower case, on this interpreter, is one other character
        in `target`.
    """
    if "pairs" not in _LOWERS_INTO:
        _LOWERS_INTO["pairs"] = [(code, ord(low)) for code in range(_MAX_CODE + 1)
                                 for low in [chr(code).lower()] if len(low) == 1 and ord(low) != code]
    return _cs_union(*[((code, code),) for code, low in _LOWERS_INTO["pairs"]
                       if _cs_has(target, low)])


class _Regex:
    """A Python regular expression as pieces. With `relax`, a construct that is not regular is
    read as a wider one and named in `not_exact`; without it, it raises `NotRegular`.

    `version` is the Python whose reading is taken, from the shipped data: one supported
    version's, or None for every supported version at once. With `native` the reading is this
    interpreter's own, every set being what its `re` matches.
    Where versions differ, or a construct is not regular, the `reading` decides: `at_least`
    takes what any version admits (and the wider construct), `at_most` what every version
    admits (and nothing for a construct that is not regular); `varies` names what differed."""

    def __init__(self, pattern: Any, flags: int = 0, relax: bool = False,
                 version: str | None = RUNNING, reading: str = "at_least",
                 native: bool = False) -> None:
        if isinstance(pattern, re.Pattern):
            pattern, flags = pattern.pattern, pattern.flags | flags
        if not isinstance(pattern, str):
            raise NotRegular(f"the pattern {pattern!r}, a bytes pattern")
        self.pattern = pattern
        self.relax = relax
        self.version = version
        self.reading = reading
        self.native = native
        self.not_exact: list[str] = []
        self.varies: list[str] = []
        self.groups: dict[int, list[Piece]] = {}
        parser, _, _ = _sre()
        try:
            re.compile(pattern, flags)
            parsed = parser.parse(pattern, flags)
        except (re.error, ValueError, TypeError) as e:
            raise NotRegular(f"the pattern {pattern!r}, which does not compile on this Python, "
                             f"{RUNNING} ({e})") from e
        self.flags = parsed.state.flags | flags
        if self.flags & re.LOCALE:
            raise NotRegular(f"the pattern {pattern!r}, under the LOCALE flag")
        self.pieces = self._seq(list(parsed), self.flags)

    def _wider(self, what: str, pieces: list[Piece]) -> list[Piece]:
        """Intent:
            Returns `pieces`, a wider reading of a construct that is not regular, noting it.

        Raises:
            NotRegular: the translation is not relaxed.
        """
        if not self.relax:
            raise NotRegular(f"the pattern {self.pattern!r} ({what})")
        if what not in self.not_exact:
            self.not_exact.append(what)
        return pieces if self.reading == "at_least" else []

    def _covered(self) -> list[str]:
        """Intent:
            Returns the Python versions this reading covers.
        """
        return versions_data()["versions"] if self.version is None else [self.version]

    def _pick(self, lo: Any, hi: Any, what: str) -> Any:
        """Intent:
            Returns the bound of a set this reading takes, noting `what` when the two differ.
        """
        if lo != hi and what not in self.varies:
            self.varies.append(what)
        return hi if self.reading == "at_least" else lo

    def _class(self, name: str, negated: bool) -> tuple[Any, Any]:
        lo, hi = class_bounds(name, self.version)
        return (_cs_complement(hi), _cs_complement(lo)) if negated else (lo, hi)

    def _structure(self, op: Any, arg: Any) -> tuple[Any, Any]:
        """Intent:
            Returns the bounds of a one-character item read without IGNORECASE or ASCII, from
            its literals and ranges and the data's sets for its categories.
        """
        name = str(op)
        if name == "LITERAL":
            return ((arg, arg),), ((arg, arg),)
        if name == "NOT_LITERAL":
            both = _cs_complement(((arg, arg),))
            return both, both
        if name == "CATEGORY":
            return self._class(*_CATEGORY_CLASS[str(arg)])
        lows, highs, negate = [], [], False
        for item_op, item in arg:
            kind = str(item_op)
            if kind == "NEGATE":
                negate = True
                continue
            if kind == "CATEGORY" and str(item) not in _CATEGORY_CLASS:
                raise NotRegular(f"the pattern {self.pattern!r} ({str(item).lower()})")
            lo, hi = (((item, item),),) * 2 if kind == "LITERAL" else (
                ((item[0], item[1]),),) * 2 if kind == "RANGE" else self._class(
                *_CATEGORY_CLASS[str(item)])
            lows.append(lo)
            highs.append(hi)
        lo, hi = _cs_union(*lows), _cs_union(*highs)
        return (_cs_complement(hi), _cs_complement(lo)) if negate else (lo, hi)

    def _leaf(self, op: Any, arg: Any, flags: int) -> Any:
        """Intent:
            Returns the code points a one-character item matches under `flags`, for this
            reading's version or versions.

        Notes:
            A native reading is what this interpreter's `re` matches. Under ASCII, and for
            `.`, every version reads alike. Without IGNORECASE the set is built from the
            item's literals and ranges and the data's category sets. Under IGNORECASE it is
            what this interpreter matches, which every version matches too unless the item
            names a character whose case reading differs between versions, or a category: then
            those characters, the categories' differing and unassigned ones, and the characters
            that lower into them, are added for `at_least` and removed for `at_most`.
        """
        name = str(op)
        if self.native or flags & re.ASCII or name == "ANY":
            return _item_chars(op, arg, flags)
        if not flags & re.IGNORECASE:
            lo, hi = self._structure(op, arg)
            return self._pick(lo, hi, "a class whose characters differ between Python versions")
        here = _item_chars(op, arg, flags)
        items = arg if name == "IN" else [(op, arg)]
        written = _cs_union(*[((a, a),) if str(o) in ("LITERAL", "NOT_LITERAL") else ((a[0], a[1]),)
                              for o, a in items if str(o) in ("LITERAL", "NOT_LITERAL", "RANGE")])
        data = versions_data()
        varying: tuple[tuple[int, int], ...] = ()
        if _cs_inter(written, data["case_varies"]):
            varying = data["case_varies"]
        if any(str(o) == "CATEGORY" for o, _ in items):
            differing = _cs_union(data["unassigned"], *[
                _cs_inter(c["any"], _cs_complement(c["common"])) for c in data["classes"].values()])
            varying = _cs_union(data["case_varies"], differing, _lowers_into(differing))
        return self._pick(_cs_inter(here, _cs_complement(varying)), _cs_union(here, varying),
                          "ignore case over characters whose case differs between Python versions")

    def _seq(self, items: Any, flags: int) -> list[Piece]:
        out = [(_TRIVIAL, _EPS, _TRIVIAL)]
        for op, arg in items:
            out = _join(out, self._item(op, arg, flags))
        return out

    def _item(self, op: Any, arg: Any, flags: int) -> list[Piece]:
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
            return [(_TRIVIAL, _chars_re(self._leaf(op, arg, flags)), _TRIVIAL)]
        if name in ("POSSESSIVE_REPEAT", "ATOMIC_GROUP") and not self.native:
            missing = [v for v in self._covered()
                       if v not in versions_data()["engine"]["possessive_and_atomic"]]
            if missing:
                raise NotRegular(
                    f"the pattern {self.pattern!r} (a possessive repeat or atomic group, which "
                    f"python {', '.join(missing)} does not read; state a version that does, "
                    f"such as python {RUNNING})")
        if name in ("MAX_REPEAT", "MIN_REPEAT", "POSSESSIVE_REPEAT"):
            lo, hi, sub = arg
            body = self._seq(sub, flags)
            if name == "POSSESSIVE_REPEAT":
                self._wider("a possessive repeat, which gives nothing back", body)
                if self.reading != "at_least":
                    return []
            return self._repeat(body, lo, None if hi == constants.MAXREPEAT else hi)
        if name == "SUBPATTERN":
            group, add, remove = arg[0], arg[1], arg[2]
            kinds = re.ASCII | re.UNICODE | re.LOCALE
            if add & kinds:
                # a scope that states ASCII or UNICODE leaves the other
                flags &= ~kinds
            pieces = self._seq(arg[-1], (flags | add) & ~remove)
            if add & re.UNICODE and self.flags & re.ASCII:
                # re.search skips a start whose character the pattern's first set, read by
                # the pattern's own flags, does not hold, so it finds no more than this reading
                pieces = self._wider("a unicode scope in an ascii pattern", pieces)
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
            # under IGNORECASE a backreference matches any text equal to the capture up to
            # case, which the group's own language need not hold
            referred = _ANY_STAR
            if group and not flags & re.IGNORECASE:
                referred = _alt(*[r for _, r, _ in group])
            return self._wider("a backreference", [(_TRIVIAL, referred, _TRIVIAL)])
        if name == "GROUPREF_EXISTS":
            _, yes, no = arg
            both = self._seq(yes, flags) + (self._seq(no, flags) if no else [(_TRIVIAL, _EPS, _TRIVIAL)])
            return self._wider("a conditional group", _merge(both))
        if name in ("ASSERT", "ASSERT_NOT"):
            what = "a lookahead" if arg[0] >= 0 else "a lookbehind"
            return self._wider(what, [(_TRIVIAL, _EPS, _TRIVIAL)])
        raise NotRegular(f"the pattern {self.pattern!r} ({name.lower()})")

    def _repeat(self, body: list[Piece], lo: int, hi: int | None) -> list[Piece]:
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
        free = _alt(*[r for _, r, _ in body])
        too_large = f"an assertion inside a repeat, too large to write out past {_WRITTEN} nodes"
        head = _power(body, lo)
        if head is None:
            return self._wider(too_large, [(_TRIVIAL, _loop(free, lo, hi), _TRIVIAL)])
        if hi is not None:
            tail = _power(_merge([*body, (_TRIVIAL, _EPS, _TRIVIAL)]), hi - lo)
            whole = None if tail is None else _join(head, tail)
            if whole is None or _written(whole) > _WRITTEN:
                return self._wider(too_large, [(_TRIVIAL, _loop(free, lo, hi), _TRIVIAL)])
            return whole
        steps = _merge([(left, _nonempty(r), right) for left, r, right in body])
        if any(left != _TRIVIAL or right != _TRIVIAL for left, _, right in steps):
            free = _alt(*[r for _, r, _ in steps])
            steps = self._wider("an anchor or word boundary inside an unbounded repeat",
                                [(_TRIVIAL, free, _TRIVIAL)])
        return _join(head, [(_TRIVIAL, _loop(steps[0][1], 0, None) if steps else _EPS, _TRIVIAL)])

    def _at(self, name: str, flags: int) -> list[Piece]:
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
            word_op, word_arg = list(parser.parse(r"\w", flags & re.ASCII))[0]
            lo = hi = _item_chars(word_op, word_arg, flags & ~re.IGNORECASE)
            holds_in_empty = [_B_IN_EMPTY]
            if not self.native:
                engine = versions_data()["engine"]["not_boundary_in_empty"]
                holds_in_empty = [v in engine for v in self._covered()]
                if not flags & re.ASCII:
                    lo, hi = class_bounds("word", self.version)
            what = "a word boundary over characters that differ between Python versions"
            word = self._pick(lo, hi, what)
            other = self._pick(_cs_complement(hi), _cs_complement(lo), what)
            negated = name == "AT_NON_BOUNDARY"
            if negated and len(set(holds_in_empty)) > 1 and "\\B in the empty string" not in self.varies:
                self.varies.append("\\B in the empty string")
            in_empty = any(holds_in_empty) if self.reading == "at_least" else all(holds_in_empty)
            return _boundary(word, other, negated, in_empty)
        raise NotRegular(f"the pattern {self.pattern!r} ({name.lower()})")

    def language(self, mode: str) -> Expr:
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

    def sets(self) -> set[Ranges]:
        """Intent:
            Returns every character set the pieces name, in bodies and contexts.
        """
        out: set[Ranges] = set()
        for left, body, right in self.pieces:
            _re_sets(body, out)
            out.update({left[1], right[1]})
        return out


# -- the term as plain data ----------------------------------------------------


#: the dialects a pattern is written in, by canonical name
DIALECTS = ("python",)


@functools.cache
def regex_deltas() -> dict[str, Any]:
    """Intent:
        Returns the regex delta table the package ships: for one dialect, the versions it
        covers, the constructs every one of them reads alike, and a row for each version of a
        construct some version reads differently, keyed by construct, dialect and version,
        with whether that version reads it (`all`, `none`, `some`) and a digest of how. A
        construct under `translated` is one the term's translation reads for each version on
        its own, by the version table's engine reading named.
    """
    raw: dict[str, Any] = json.loads((Path(__file__).parent / "data" / "regex_deltas.json").read_text())
    return raw


#: the construct each parse operation is, by the operation's name
_CONSTRUCTS = {
    "LITERAL": "literal", "NOT_LITERAL": "literal", "ANY": "any character", "IN": "character set",
    "RANGE": "character set", "NEGATE": "character set", "CATEGORY": "character set",
    "BRANCH": "alternation", "SUBPATTERN": "group", "MAX_REPEAT": "greedy repeat",
    "MIN_REPEAT": "lazy repeat", "POSSESSIVE_REPEAT": "possessive repeat",
    "ATOMIC_GROUP": "atomic group", "GROUPREF": "backreference",
    "GROUPREF_EXISTS": "conditional"}

#: the construct each position assertion is, by its code's name
_POSITIONS = {
    "AT_BEGINNING": "start of line", "AT_BEGINNING_LINE": "start of line",
    "AT_END": "end of line", "AT_END_LINE": "end of line",
    "AT_BEGINNING_STRING": "start of text", "AT_END_STRING": "end of text",
    "AT_BOUNDARY": "word boundary", "AT_NON_BOUNDARY": "not a word boundary"}

#: the construct each flag is, as an argument or written inline
_FLAG_CONSTRUCTS = {re.IGNORECASE: "ignore case", re.MULTILINE: "multi line",
                    re.DOTALL: "dot all", re.ASCII: "ascii only", re.VERBOSE: "verbose"}
_FLAG_LETTERS = {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL, "a": re.ASCII,
                 "x": re.VERBOSE}


def _parsed_constructs(tree: Any) -> set[str]:
    """Intent:
        Returns the constructs a parsed pattern uses, nested ones included; an operation the
        table does not name is returned as its own name.
    """
    out: set[str] = set()
    stack: list[Any] = [tree]
    while stack:
        node = stack.pop()
        items = list(node.data) if hasattr(node, "data") else list(node)
        for item in items:
            if not (isinstance(item, tuple) and len(item) == 2):
                continue
            op, arg = str(item[0]), item[1]
            if op == "AT":
                out.add(_POSITIONS.get(str(arg), str(arg)))
            elif op in ("ASSERT", "ASSERT_NOT"):
                out.add("lookahead" if arg[0] == 1 else "lookbehind")
                stack.append(arg[1])
            elif op == "SUBPATTERN":
                out.add("group")
                if arg[1] or arg[2]:
                    out.add("scoped flags")
                    out |= {name for flag, name in _FLAG_CONSTRUCTS.items() if (arg[1] | arg[2]) & flag}
                stack.append(arg[-1])
            else:
                out.add(_CONSTRUCTS.get(op, op))
                if op in ("IN", "BRANCH"):
                    stack.append(arg if op == "IN" else [x for branch in arg[1] for x in branch])
                elif op in ("MAX_REPEAT", "MIN_REPEAT", "POSSESSIVE_REPEAT"):
                    stack.append(arg[2])
                elif op == "ATOMIC_GROUP":
                    stack.append(arg)
                elif op == "GROUPREF_EXISTS":
                    stack += [branch for branch in arg[1:] if branch is not None]
    return out


def _written_constructs(pattern: str) -> set[str]:
    """Intent:
        Returns the constructs a pattern's text shows that its parse does not: inline flag
        groups at the start and after it, the end of text written `\\z`, a character written
        by its name `\\N{...}`, and a conditional group referred to by a non-ASCII digit or by
        a reference that is neither ASCII digits nor a name (`(?(+1)...)`, `(?( 1)...)`).
    """
    out: set[str] = set()
    lead = re.match(r"(?:\(\?[aiLmsux]+\))+", pattern)
    if lead is not None:
        out.add("inline flags at the start")
        for letter in re.sub(r"[(?)]", "", lead.group(0)):
            if letter in _FLAG_LETTERS:
                out.add(_FLAG_CONSTRUCTS[_FLAG_LETTERS[letter]])
    at, inside = 0 if lead is None else lead.end(), False
    while at < len(pattern):
        ch = pattern[at]
        if ch == "\\":
            if not inside and pattern[at + 1:at + 2] == "z":
                out.add("end of text, written \\z")
            if pattern[at + 1:at + 3] == "N{":
                out.add("named character")
            at += 2
            continue
        if inside:
            inside = ch != "]"
        elif ch == "[":
            inside = True
            at += 1
            if pattern[at:at + 1] == "^":
                at += 1
            if pattern[at:at + 1] == "]":
                at += 1
            continue
        elif re.match(r"\(\?[aiLmsux]+\)", pattern[at:]):
            out.add("inline flags after the start")
        elif pattern.startswith("(?(", at):
            reference = pattern[at + 3:pattern.find(")", at + 3)]
            if any(c.isdigit() and not c.isascii() for c in reference):
                out.add("group reference by a non-ASCII digit")
            elif not (reference.isascii() and reference.isdigit()) and not reference.isidentifier():
                out.add("group reference written loosely")
        at += 1
    return out


def constructs(pattern: str, flags: int = 0) -> set[str]:
    """Intent:
        Returns the constructs a pattern uses under `flags`, by the regex delta table's names,
        from this interpreter's parse of it and from its text.

    Raises:
        NotRegular: the pattern does not compile here.
    """
    import warnings
    parser, _, _ = _sre()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            tree = parser.parse(pattern, flags)
        except (re.error, RecursionError, OverflowError) as e:
            raise NotRegular(f"the pattern {pattern!r} does not compile on this Python: {e}") from e
    out = _parsed_constructs(tree) | _written_constructs(pattern)
    return out | {name for flag, name in _FLAG_CONSTRUCTS.items() if flags & flag}


def other_version_problem(pattern: str, flags: int, versions: list[str]) -> str | None:
    """Intent:
        Returns why a pattern parsed by this interpreter's `re` cannot be read for `versions`,
        or None when it can: every one of them is this Python, or every construct the pattern
        uses is shown by the regex delta table to read alike here and on each of them (listed
        as read alike, or with rows of the same reading, or translated for each version on its
        own). A construct the table does not name is not shown to read alike, so it is refused
        for any other version, as is everything on an interpreter the table does not cover. A
        character written by its name (`\\N{...}`) is refused for every version, this one
        included: patch releases of one Python read different names.

    Raises:
        NotRegular: the pattern does not compile here.
    """
    used = constructs(pattern, flags)
    if "named character" in used:
        return (f"the pattern {pattern!r} writes a character by its name, which patch releases of "
                f"one Python read differently, so it is read only by this interpreter's own re, "
                f"never for a stated version or for every supported Python")
    others = [v for v in versions if v != RUNNING]
    if not others:
        return None
    table = regex_deltas()
    if RUNNING not in table["versions"]:
        return (f"the pattern {pattern!r} is read here by python {RUNNING}, which the regex delta "
                f"table does not cover, so it cannot be read for python {', '.join(others)}")
    rows = {(r["construct"], r["version"]): r for r in table["rows"] if r["dialect"] == "python"}
    named = {r["construct"] for r in table["rows"]} | set(table["read_alike"])
    for construct in sorted(used):
        if construct not in named:
            return (f"the pattern {pattern!r} uses {construct}, which the regex delta table "
                    f"does not show read alike on python {', '.join(others)}")
        if construct in table["read_alike"] or construct in table["translated"]:
            continue
        here = rows[(construct, RUNNING)]
        for version in others:
            there = rows.get((construct, version))
            if there is None:
                return (f"the pattern {pattern!r} uses {construct}, which the regex delta table "
                        f"does not record for python {version}")
            if there["reads"] == "none":
                return (f"the pattern {pattern!r} uses {construct}, which python {version} does "
                        f"not read; state a version that does, such as python {RUNNING}")
            if there["digest"] != here["digest"]:
                return (f"the pattern {pattern!r} uses {construct}, which python {version} reads "
                        f"differently from python {RUNNING}; state python {RUNNING}")
    return None


def term(pattern: Any, flags: Any = 0, predicate: str = "matches", dialect: str = "python",
         version: str | None = None) -> Node:
    """Intent:
        Returns the term of the strings for which `predicate` holds of a pattern under `flags`,
        on every supported Python, or on the one `version` names (`"3.13"`): exact where one
        regular language is the answer, else an at-least and at-most pair. Without a version
        the pair brackets every supported version: `at_most` holds only strings every version
        admits, `at_least` every string any version admits; a class's characters that differ
        between versions, and code points still unassigned, fall between the two. The term is
        the same whichever supported interpreter builds it.

    Notes:
        A pattern is parsed by the running interpreter, so a pattern its `re` does not compile
        is refused here whatever version is asked for: a possessive repeat or an atomic group
        on Python 3.10, which reads neither. On a later interpreter the same pattern is
        refused for version 3.10, and without a version, since 3.10 is one of the Pythons the
        term would have to hold on; with a version of 3.11 or later it is a bound. For any
        version other than this one, a pattern is read only where `other_version_problem`
        finds every construct read alike there: global flags after the start, which 3.10
        reads with a warning and 3.11 refuses, are refused for every other version.

    Raises:
        NotRegular: the pattern does not compile, is a bytes pattern, uses LOCALE, or uses a
            construct some of the versions it is about read differently or not at all.
        ValueError: `predicate` is not one of `PREDICATES`, `dialect` not one of `DIALECTS`, or
            `version` not a supported Python.
    """
    if predicate not in PREDICATES:
        raise ValueError(f"a predicate is one of {sorted(PREDICATES)}, not {predicate!r}")
    if dialect not in DIALECTS:
        raise ValueError(f"a dialect is one of {list(DIALECTS)}, not {dialect!r}")
    data = versions_data()
    if version is not None and version not in data["versions"]:
        raise ValueError(f"python {version} is not one of the supported versions {data['versions']}")
    key = (pattern, int(flags), predicate, version)
    if key in _TERMS:
        import copy
        return copy.deepcopy(_TERMS[key])
    text = pattern.pattern if isinstance(pattern, re.Pattern) else pattern
    if isinstance(text, str):
        problem = other_version_problem(
            text, int(flags) | (int(pattern.flags) if isinstance(pattern, re.Pattern) else 0),
            data["versions"] if version is None else [version])
        if problem is not None:
            raise NotRegular(problem)
    high = _Regex(pattern, int(flags), relax=True, version=version, reading="at_least")
    low = _Regex(pattern, int(flags), relax=True, version=version, reading="at_most")
    at_least = to_node(high.language(PREDICATES[predicate]))
    at_most = to_node(low.language(PREDICATES[predicate]))
    covered = data["versions"] if version is None else [version]
    source: dict[str, Any] = {
        "dialect": dialect, "versions": covered,
        "unicode": list(dict.fromkeys(data["unicode"][v] for v in covered)),
        "pattern": pattern.pattern if isinstance(pattern, re.Pattern) else pattern,
        "flags": sorted(word for flag, word in FLAG_WORDS.items() if high.flags & flag),
        "predicate": predicate}
    doc: dict[str, Any] = {
        "kind": "regular_language", "version": TERM_VERSION, "alphabet": [[0, _MAX_CODE]],
        "exact": at_least == at_most, "source": source}
    if doc["exact"]:
        doc["language"] = at_least
    else:
        doc["at_least"] = at_least
        doc["at_most"] = at_most
        doc["source"]["not_exact"] = [*high.not_exact, *high.varies]
    if len(_TERMS) > 512:
        _TERMS.clear()
    import copy
    _TERMS[key] = copy.deepcopy(doc)
    return doc


_TERMS: dict[tuple[Any, int, str, Any], Node] = {}


def under_predicate(doc: Node, predicate: str) -> Node:
    """Intent:
        Returns the term of the strings for which `predicate` holds of a term read in full
        (`matches`): the term itself, with any text before it (`ends with`), after it
        (`starts with`) or on both sides (`contains`), each bound alike.

    Raises:
        ValueError: `predicate` is not one of `PREDICATES`.
    """
    import copy
    if predicate not in PREDICATES:
        raise ValueError(f"a predicate is one of {sorted(PREDICATES)}, not {predicate!r}")
    anything = _loop(_chars_re(_FULL), 0, None)
    before = anything if predicate in ("contains", "ends with") else _EPS
    after = anything if predicate in ("contains", "starts with") else _EPS
    out = copy.deepcopy(doc)
    for key in ("language", "at_least", "at_most"):
        if key in out:
            out[key] = to_node(_cat(before, from_node(out[key]), after))
    if not out["exact"] and out["at_least"] == out["at_most"]:
        out["exact"], out["language"] = True, out.pop("at_least")
        del out["at_most"]
    out.setdefault("source", {})["predicate"] = predicate
    return out


# -- membership by derivatives -------------------------------------------------


def runs(pattern: Any, flags: int, predicate: str, text: str) -> bool:
    """Intent:
        Returns whether `predicate` holds of `text` for the pattern, by running `re`: `matches`
        is `fullmatch`, `contains` is `search`, `starts with` is `match`, and `ends with` is a
        `fullmatch` from some position to the end, read in the whole string.
    """
    compiled = re.compile(pattern, flags)
    if predicate == "matches":
        return compiled.fullmatch(text) is not None
    if predicate == "contains":
        return compiled.search(text) is not None
    if predicate == "starts with":
        return compiled.match(text) is not None
    if predicate == "ends with":
        return any(compiled.fullmatch(text, i) is not None for i in range(len(text) + 1))
    raise ValueError(f"a predicate is one of {sorted(PREDICATES)}, not {predicate!r}")


def admits(pattern: Any, flags: Any, predicate: str, text: str, dialect: str = "python",
           bound: str = "at_least", version: str = "running") -> bool:
    r"""Intent:
        Returns whether `text` is in the term of the pattern under `predicate`: its language
        when exact, else the `bound` named, `at_least` or `at_most`. The term is this
        interpreter's version's (`running`), a named version's (`"3.13"`), or the one for every
        supported version (`every`).

    Claims:
        dollar_agrees_with_re: let runs = mathema_language.text._regular.runs, for text in {"", "a", "\n", "aa", "a\n", "\na", "\n\n", "aaa", "aa\n", "a\na", "a\n\n", "\naa", "\na\n", "\n\na", "\n\n\n"}, f("a$", 0, "matches", text) == runs("a$", 0, "matches", text)
        search_agrees_with_re: let runs = mathema_language.text._regular.runs, for text in {"", "a", "b", "\n", "aa", "ab", "a\n", "ba", "bb", "b\n", "\na", "\nb", "\n\n", "aaa", "aab", "aa\n", "aba", "abb", "ab\n", "a\na", "a\nb", "a\n\n", "baa", "bab", "ba\n", "bba", "bbb", "bb\n", "b\na", "b\nb", "b\n\n", "\naa", "\nab", "\na\n", "\nba", "\nbb", "\nb\n", "\n\na", "\n\nb", "\n\n\n"}, f("\\Aa$", 0, "contains", text) == runs("\\Aa$", 0, "contains", text)
        match_agrees_with_re: let runs = mathema_language.text._regular.runs, for text in {"", "a", "A", "1", "\n", "aa", "aA", "a1", "a\n", "Aa", "AA", "A1", "A\n", "1a", "1A", "11", "1\n", "\na", "\nA", "\n1", "\n\n", "aaa", "aaA", "aa1", "aa\n", "aAa", "aAA", "aA1", "aA\n", "a1a", "a1A", "a11", "a1\n", "a\na", "a\nA", "a\n1", "a\n\n", "Aaa", "AaA", "Aa1", "Aa\n", "AAa", "AAA", "AA1", "AA\n", "A1a", "A1A", "A11", "A1\n", "A\na", "A\nA", "A\n1", "A\n\n", "1aa", "1aA", "1a1", "1a\n", "1Aa", "1AA", "1A1", "1A\n", "11a", "11A", "111", "11\n", "1\na", "1\nA", "1\n1", "1\n\n", "\naa", "\naA", "\na1", "\na\n", "\nAa", "\nAA", "\nA1", "\nA\n", "\n1a", "\n1A", "\n11", "\n1\n", "\n\na", "\n\nA", "\n\n1", "\n\n\n"}, f("[a-z]+", 2, "starts with", text) == runs("[a-z]+", 2, "starts with", text)
        ends_with_agrees_with_re: let runs = mathema_language.text._regular.runs, for text in {"", "a", "b", "\n", "aa", "ab", "a\n", "ba", "bb", "b\n", "\na", "\nb", "\n\n", "aaa", "aab", "aa\n", "aba", "abb", "ab\n", "a\na", "a\nb", "a\n\n", "baa", "bab", "ba\n", "bba", "bbb", "bb\n", "b\na", "b\nb", "b\n\n", "\naa", "\nab", "\na\n", "\nba", "\nbb", "\nb\n", "\n\na", "\n\nb", "\n\n\n"}, f("^b$", 8, "ends with", text) == runs("^b$", 8, "ends with", text)
        words_agree_with_re: let runs = mathema_language.text._regular.runs, for text in {"", "a", " ", "\u00b2", "\n", "aa", "a ", "a\u00b2", "a\n", " a", "  ", " \u00b2", " \n", "\u00b2a", "\u00b2 ", "\u00b2\u00b2", "\u00b2\n", "\na", "\n ", "\n\u00b2", "\n\n", "aaa", "aa ", "aa\u00b2", "aa\n", "a a", "a  ", "a \u00b2", "a \n", "a\u00b2a", "a\u00b2 ", "a\u00b2\u00b2", "a\u00b2\n", "a\na", "a\n ", "a\n\u00b2", "a\n\n", " aa", " a ", " a\u00b2", " a\n", "  a", "   ", "  \u00b2", "  \n", " \u00b2a", " \u00b2 ", " \u00b2\u00b2", " \u00b2\n", " \na", " \n ", " \n\u00b2", " \n\n", "\u00b2aa", "\u00b2a ", "\u00b2a\u00b2", "\u00b2a\n", "\u00b2 a", "\u00b2  ", "\u00b2 \u00b2", "\u00b2 \n", "\u00b2\u00b2a", "\u00b2\u00b2 ", "\u00b2\u00b2\u00b2", "\u00b2\u00b2\n", "\u00b2\na", "\u00b2\n ", "\u00b2\n\u00b2", "\u00b2\n\n", "\naa", "\na ", "\na\u00b2", "\na\n", "\n a", "\n  ", "\n \u00b2", "\n \n", "\n\u00b2a", "\n\u00b2 ", "\n\u00b2\u00b2", "\n\u00b2\n", "\n\na", "\n\n ", "\n\n\u00b2", "\n\n\n"}, f("\\b\\w+\\b", 0, "contains", text) == runs("\\b\\w+\\b", 0, "contains", text)
        digits_agree_with_re: let runs = mathema_language.text._regular.runs, for text in {"", "1", ".", "\u0663", "\n", "11", "1.", "1\u0663", "1\n", ".1", "..", ".\u0663", ".\n", "\u06631", "\u0663.", "\u0663\u0663", "\u0663\n", "\n1", "\n.", "\n\u0663", "\n\n", "111", "11.", "11\u0663", "11\n", "1.1", "1..", "1.\u0663", "1.\n", "1\u06631", "1\u0663.", "1\u0663\u0663", "1\u0663\n", "1\n1", "1\n.", "1\n\u0663", "1\n\n", ".11", ".1.", ".1\u0663", ".1\n", "..1", "...", "..\u0663", "..\n", ".\u06631", ".\u0663.", ".\u0663\u0663", ".\u0663\n", ".\n1", ".\n.", ".\n\u0663", ".\n\n", "\u066311", "\u06631.", "\u06631\u0663", "\u06631\n", "\u0663.1", "\u0663..", "\u0663.\u0663", "\u0663.\n", "\u0663\u06631", "\u0663\u0663.", "\u0663\u0663\u0663", "\u0663\u0663\n", "\u0663\n1", "\u0663\n.", "\u0663\n\u0663", "\u0663\n\n", "\n11", "\n1.", "\n1\u0663", "\n1\n", "\n.1", "\n..", "\n.\u0663", "\n.\n", "\n\u06631", "\n\u0663.", "\n\u0663\u0663", "\n\u0663\n", "\n\n1", "\n\n.", "\n\n\u0663", "\n\n\n"}, f("\\d+(?:\\.\\d+)?", 0, "matches", text) == runs("\\d+(?:\\.\\d+)?", 0, "matches", text)
        scoped_ascii_agrees_with_re: let runs = mathema_language.text._regular.runs, for text in {"", "a", "\u017f", "\n", "aa", "a\u017f", "a\n", "\u017fa", "\u017f\u017f", "\u017f\n", "\na", "\n\u017f", "\n\n", "aaa", "aa\u017f", "aa\n", "a\u017fa", "a\u017f\u017f", "a\u017f\n", "a\na", "a\n\u017f", "a\n\n", "\u017faa", "\u017fa\u017f", "\u017fa\n", "\u017f\u017fa", "\u017f\u017f\u017f", "\u017f\u017f\n", "\u017f\na", "\u017f\n\u017f", "\u017f\n\n", "\naa", "\na\u017f", "\na\n", "\n\u017fa", "\n\u017f\u017f", "\n\u017f\n", "\n\na", "\n\n\u017f", "\n\n\n"}, f("(?a:\\w)\\w", 0, "matches", text) == runs("(?a:\\w)\\w", 0, "matches", text)
        a_backreference_is_bounded_below: let runs = mathema_language.text._regular.runs, for text in {"", "a", "A", "\n", "aa", "aA", "a\n", "Aa", "AA", "A\n", "\na", "\nA", "\n\n", "aaa", "aaA", "aa\n", "aAa", "aAA", "aA\n", "a\na", "a\nA", "a\n\n", "Aaa", "AaA", "Aa\n", "AAa", "AAA", "AA\n", "A\na", "A\nA", "A\n\n", "\naa", "\naA", "\na\n", "\nAa", "\nAA", "\nA\n", "\n\na", "\n\nA", "\n\n\n"}, (f("(a+)(?i:\\1)", 0, "matches", text, "python", "at_least") or not runs("(a+)(?i:\\1)", 0, "matches", text)) == True
        a_backreference_is_bounded_above: let runs = mathema_language.text._regular.runs, for text in {"", "a", "A", "\n", "aa", "aA", "a\n", "Aa", "AA", "A\n", "\na", "\nA", "\n\n", "aaa", "aaA", "aa\n", "aAa", "aAA", "aA\n", "a\na", "a\nA", "a\n\n", "Aaa", "AaA", "Aa\n", "AAa", "AAA", "AA\n", "A\na", "A\nA", "A\n\n", "\naa", "\naA", "\na\n", "\nAa", "\nAA", "\nA\n", "\n\na", "\n\nA", "\n\n\n"}, (runs("(a+)(?i:\\1)", 0, "matches", text) or not f("(a+)(?i:\\1)", 0, "matches", text, "python", "at_most")) == True
        the_json_round_trip_keeps_membership: let again = mathema_language.text._regular.admits_after_json, for text in {"", "a", "b", "\n", "aa", "ab", "a\n", "ba", "bb", "b\n", "\na", "\nb", "\n\n", "aaa", "aab", "aa\n", "aba", "abb", "ab\n", "a\na", "a\nb", "a\n\n", "baa", "bab", "ba\n", "bba", "bbb", "bb\n", "b\na", "b\nb", "b\n\n", "\naa", "\nab", "\na\n", "\nba", "\nbb", "\nb\n", "\n\na", "\n\nb", "\n\n\n"}, f("^a(?:b|$)", 8, "contains", text) == again("^a(?:b|$)", 8, "contains", text)
        every_version_holds_what_re_admits: let runs = mathema_language.text._regular.runs, for text in {"", "a", " ", "\u00b2", "\n", "aa", "a ", "a\u00b2", "a\n", " a", "  ", " \u00b2", " \n", "\u00b2a", "\u00b2 ", "\u00b2\u00b2", "\u00b2\n", "\na", "\n ", "\n\u00b2", "\n\n", "aaa", "aa ", "aa\u00b2", "aa\n", "a a", "a  ", "a \u00b2", "a \n", "a\u00b2a", "a\u00b2 ", "a\u00b2\u00b2", "a\u00b2\n", "a\na", "a\n ", "a\n\u00b2", "a\n\n", " aa", " a ", " a\u00b2", " a\n", "  a", "   ", "  \u00b2", "  \n", " \u00b2a", " \u00b2 ", " \u00b2\u00b2", " \u00b2\n", " \na", " \n ", " \n\u00b2", " \n\n", "\u00b2aa", "\u00b2a ", "\u00b2a\u00b2", "\u00b2a\n", "\u00b2 a", "\u00b2  ", "\u00b2 \u00b2", "\u00b2 \n", "\u00b2\u00b2a", "\u00b2\u00b2 ", "\u00b2\u00b2\u00b2", "\u00b2\u00b2\n", "\u00b2\na", "\u00b2\n ", "\u00b2\n\u00b2", "\u00b2\n\n", "\naa", "\na ", "\na\u00b2", "\na\n", "\n a", "\n  ", "\n \u00b2", "\n \n", "\n\u00b2a", "\n\u00b2 ", "\n\u00b2\u00b2", "\n\u00b2\n", "\n\na", "\n\n ", "\n\n\u00b2", "\n\n\n"}, (f("\\b\\w+\\b", 0, "contains", text, "python", "at_least", "every") or not runs("\\b\\w+\\b", 0, "contains", text)) == True
        every_version_admits_what_the_lower_bound_holds: let runs = mathema_language.text._regular.runs, for text in {"", "a", " ", "\u00b2", "\n", "aa", "a ", "a\u00b2", "a\n", " a", "  ", " \u00b2", " \n", "\u00b2a", "\u00b2 ", "\u00b2\u00b2", "\u00b2\n", "\na", "\n ", "\n\u00b2", "\n\n", "aaa", "aa ", "aa\u00b2", "aa\n", "a a", "a  ", "a \u00b2", "a \n", "a\u00b2a", "a\u00b2 ", "a\u00b2\u00b2", "a\u00b2\n", "a\na", "a\n ", "a\n\u00b2", "a\n\n", " aa", " a ", " a\u00b2", " a\n", "  a", "   ", "  \u00b2", "  \n", " \u00b2a", " \u00b2 ", " \u00b2\u00b2", " \u00b2\n", " \na", " \n ", " \n\u00b2", " \n\n", "\u00b2aa", "\u00b2a ", "\u00b2a\u00b2", "\u00b2a\n", "\u00b2 a", "\u00b2  ", "\u00b2 \u00b2", "\u00b2 \n", "\u00b2\u00b2a", "\u00b2\u00b2 ", "\u00b2\u00b2\u00b2", "\u00b2\u00b2\n", "\u00b2\na", "\u00b2\n ", "\u00b2\n\u00b2", "\u00b2\n\n", "\naa", "\na ", "\na\u00b2", "\na\n", "\n a", "\n  ", "\n \u00b2", "\n \n", "\n\u00b2a", "\n\u00b2 ", "\n\u00b2\u00b2", "\n\u00b2\n", "\n\na", "\n\n ", "\n\n\u00b2", "\n\n\n"}, (runs("\\b\\w+\\b", 0, "contains", text) or not f("\\b\\w+\\b", 0, "contains", text, "python", "at_most", "every")) == True

    Raises:
        NotRegular: the pattern does not compile, is a bytes pattern, or uses LOCALE.
    """
    key = (pattern, flags, predicate, dialect, bound, version)
    if key not in _ADMITTED:
        pinned = {"running": RUNNING, "every": None}.get(version, version)
        doc = term(pattern, flags, predicate, dialect, pinned)
        units = doc["alphabet"] == [[0, 0xFFFF]]
        _ADMITTED[key] = (from_node(doc["language"] if doc["exact"] else doc[bound]), units)
    expression, units = _ADMITTED[key]
    return holds(expression, code_units(text) if units else text)


def admits_after_json(pattern: Any, flags: Any, predicate: str, text: str) -> bool:
    """Intent:
        Returns whether `text` is in the at-least reading of the pattern's term after the term
        is written as JSON text and read back.
    """
    import json
    doc = json.loads(json.dumps(term(pattern, flags, predicate, version=RUNNING), ensure_ascii=True))
    return member(doc, text, "at_least")


def exact(pattern: Any, flags: Any = 0, predicate: str = "matches", dialect: str = "python",
          version: str = "every") -> bool:
    r"""Intent:
        Returns whether the pattern's term under `predicate` is exact, for every supported
        Python (`every`) or for the one `version` names (`"3.13"`).

    Claims:
        anchors_and_flags_are_exact: f("(?m)^a$|\\Ab\\Z", 2) == True
        unicode_classes_are_exact_on_one_version: f("\\b\\w+\\s\\d", 0, "contains", "python", "3.13") == True
        unicode_classes_differ_between_versions: f("\\b\\w+\\s\\d", 0, "contains") == False
        ascii_classes_are_exact_on_every_version: f("\\b\\w+\\s\\d", 256, "contains") == True
        ignore_case_is_exact_on_every_version: f("[a-z]+k", 2, "contains") == True
        not_boundary_differs_between_versions: f("\\B", 256, "matches") == False
        a_backreference_is_not: f("(a)\\1", 0) == False
        a_lookahead_is_not: f("(?=a)a", 0, "contains") == False
        a_possessive_repeat_is_not: f("a*+a", 0, "matches", "python", "3.13") == False

    Raises:
        NotRegular: the pattern does not compile.
    """
    return bool(term(pattern, flags, predicate, dialect, None if version == "every" else version)["exact"])


def canonical_is_stable(pattern: Any, flags: Any = 0, predicate: str = "matches",
                        dialect: str = "python") -> bool:
    r"""Intent:
        Returns whether the canonical form of each node of the pattern's term is its own
        canonical form, and the term's hash is unchanged by canonicalising its nodes.

    Claims:
        an_anchored_pattern: f("^a(?:b|$)", 8, "contains") == True
        a_unicode_class: f("\\b\\w+\\b", 0, "ends with") == True
        a_bounded_pair: f("(a)\\1|b", 0, "matches") == True
    """
    doc = term(pattern, flags, predicate, dialect)
    again = dict(doc)
    for key in ("language", "at_least", "at_most"):
        if key in doc:
            once = canonical(doc[key])
            if canonical(once) != once:
                return False
            again[key] = once
    return term_hash(again) == term_hash(doc)


_ADMITTED: dict[tuple[Any, Any, str, str, str, str], tuple[Expr, bool]] = {}


def every_string_over_class(name: str) -> Node:
    """Intent:
        Returns the term of every string over a class whose characters depend on the Python
        version, for every supported version: `at_most` over the characters all versions
        hold, `at_least` over those any holds and the unassigned code points.
    """
    data = versions_data()
    low, high = class_bounds(name)

    def star(chars: Any) -> Node:
        return canonical({"op": "repeat", "min": 0, "max": None,
                          "arg": {"op": "chars", "ranges": [[lo, hi] for lo, hi in chars]}})

    return {"kind": "regular_language", "version": TERM_VERSION, "alphabet": [[0, _MAX_CODE]],
            "exact": False, "at_least": star(high), "at_most": star(low),
            "source": {"alphabet": name, "dialect": "python", "versions": data["versions"],
                       "unicode": list(dict.fromkeys(data["unicode"].values())),
                       "not_exact": ["a class whose characters differ between Python versions"]}}


#: the predicate a compiled pattern's method reads
_METHODS = {"fullmatch": "matches", "search": "contains", "match": "starts with"}


#: the characters drawn beside a match
_BESIDE = "xyz XYZ019-_.é\n"


def beside(rng: Any, predicate: str, text: str) -> str:
    """Intent:
        Returns `text` with text drawn beside it where the predicate allows it, half the time:
        for `contains` before it, after it or both, so a match anchored at one end still gets
        text on its open side; after it for `starts with`; before it for `ends with`; never for
        `matches`. The text beside is up to four characters of a small pool.
    """
    if predicate == "matches" or rng.random() < 0.5:
        return text

    def some() -> str:
        return "".join(rng.choice(_BESIDE) for _ in range(rng.randint(1, 4)))
    sides = {"contains": rng.choice([(True, True), (True, False), (False, True)]),
             "starts with": (False, True), "ends with": (True, False)}[predicate]
    return (some() if sides[0] else "") + text + (some() if sides[1] else "")


def pattern_language(source: Any, predicate: str | None = None, flags: int = 0,
                     version: str | None = None) -> Any:
    """Intent:
        Returns `regex_language(source, predicate, flags, version)`, under the name 0.4.0
        gave it, with a `DeprecationWarning` naming `regex_language`. The name goes in 0.5.0.
    """
    import warnings
    warnings.warn("pattern_language is now regex_language; the old name goes in 0.5.0",
                  DeprecationWarning, stacklevel=2)
    return regex_language(source, predicate, flags, version)


def regex_language(source: Any, predicate: str | None = None, flags: int = 0,
                     version: str | None = None) -> Any:
    """Intent:
        Returns the text language of the strings a predicate holds of a Python pattern:
        membership by `re` itself, the term as its stated `term`, draws from the
        pattern's parse tree, with text beside the match half the time where the predicate
        allows it (`beside`), or, failing that, a shortest member of the term. `source` is a
        compiled pattern, a pattern's text (with `flags`), or a compiled pattern's bound
        method `fullmatch`, `search` or `match`, which names its own predicate; the predicate
        is `matches` when none is given or named. Without a `version` the language is about
        every supported Python and its definition brackets them; with one (`"3.13"`) it is
        about that Python alone, and on another interpreter it refuses to be checked or drawn,
        since `re` here is not the `re` the claim is about.

    Raises:
        NotRegular: the pattern is a bytes pattern or does not compile.
        ValueError: `predicate` is not one of `PREDICATES`, or is not the one a bound method
            names.
    """
    import random as _random

    from ._kit import PinnedLanguage, TextLanguage
    from .regex import Unsupported, _emit

    owner = getattr(source, "__self__", None)
    if isinstance(owner, re.Pattern):
        named = _METHODS.get(getattr(source, "__name__", ""))
        if named is None:
            raise ValueError(f"{source!r} is not a pattern's fullmatch, search or match")
        if predicate not in (None, named):
            raise ValueError(f"{source.__name__} reads as {named!r}, not {predicate!r}")
        source, predicate = owner, named
    predicate = predicate or "matches"
    if isinstance(source, re.Pattern):
        pattern, flags = source.pattern, source.flags | int(flags)
    else:
        pattern = source
    doc = term(pattern, flags, predicate, version=version)
    words = [*doc["source"]["flags"], *([f"python {version}"] if version else [])]
    name = f"{predicate} (re({pattern!r}{''.join(', ' + w for w in words)}))"
    elsewhere = version is not None and version != RUNNING
    parser, _, _ = _sre()
    tree = parser.parse(pattern, flags)
    fallback = shortest(from_node(doc["language"])) if doc["exact"] else None

    def accepts(text: str) -> bool:
        return runs(pattern, flags, predicate, text)

    def draw(rng: _random.Random) -> str:
        for _ in range(40):
            try:
                text = beside(rng, predicate, _emit(rng, tree, {}))
            except Unsupported:
                break
            if accepts(text):
                return text
        if fallback is not None and accepts(fallback):
            return fallback
        raise ValueError(f"no member of {name} was drawn")

    if elsewhere:
        return PinnedLanguage(name, level="predicate", accepts=accepts, generate=draw,
                              schema={"term": doc},
                              elsewhere=f"this claim is about python {version}; this is python {RUNNING}")
    return TextLanguage(name, level="predicate", accepts=accepts, generate=draw,
                        schema={"term": doc})
