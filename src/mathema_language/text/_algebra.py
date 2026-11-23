# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The algebra of regular-language terms: what a term is, apart from
any pattern dialect that compiles to one.

A term is a JSON document: its `version`, the `alphabet` its strings are
over, whether it is `exact`, and its `language` as a node, or an
`at_least` and an `at_most` node when one regular language is not the
answer. A node is `empty`, `epsilon`, a `literal` of code points, a
`chars` set of code point ranges, or a `concat`, `union`, `inter`,
`complement` or `repeat` of nodes. This module holds what is true of
every such term: sets of code points as sorted ranges, the expression
form a node is read into and its constructors, the canonical form of a
node (`canonical`), the text and SHA-256 that identify a term's meaning
(`canonical_text`, `term_hash`), membership of a string by derivatives
(`holds`, `member`), the character sets an expression tells apart
(`_re_sets`), its shortest string (`shortest`), and the terms built
from others (`every_string_over`, `of_length`).

Every other module reads the algebra through this one. The compiler of
Python `re` patterns to terms is `_regular`.
"""
from __future__ import annotations

import re
from typing import Any

#: the version of the term's schema
TERM_VERSION = 1


#: code points as sorted, disjoint, inclusive ranges
Ranges = tuple[tuple[int, int], ...]


#: a regular expression before it is written as a term: a tuple of a kind and its parts
Expr = tuple[Any, ...]


#: a term node or document, as plain JSON data
Node = dict[str, Any]


#: the last code point
_MAX_CODE = 0x10FFFF


#: every code point
_FULL: tuple[tuple[int, int], ...] = ((0, _MAX_CODE),)


#: the empty set
_NONE: tuple[tuple[int, int], ...] = ()


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


# a regular expression, before z3: ("chars", set), ("eps",), ("empty",),
# ("cat", a, b, ...), ("alt", a, b, ...), ("loop", r, lo, hi or None),
# ("inter", a, b)
_EPS: Expr = ("eps",)


_EMPTY_RE: Expr = ("empty",)


_ANY_STAR: Expr = ("loop", ("chars", _FULL), 0, None)


_ANY_PLUS: Expr = ("loop", ("chars", _FULL), 1, None)


def _chars_re(s: Any) -> Expr:
    return ("chars", tuple(s)) if s else _EMPTY_RE


def _cat(*parts: Expr) -> Expr:
    flat: list[Expr] = []
    for p in parts:
        if p == _EMPTY_RE:
            return _EMPTY_RE
        if p == _EPS:
            continue
        flat.extend(p[1:] if p[0] == "cat" else [p])
    if not flat:
        return _EPS
    return flat[0] if len(flat) == 1 else ("cat", *flat)


def _alt(*parts: Expr) -> Expr:
    flat: list[Expr] = []
    for p in parts:
        for q in (p[1:] if p[0] == "alt" else [p]):
            if q != _EMPTY_RE and q not in flat:
                flat.append(q)
    if not flat:
        return _EMPTY_RE
    return flat[0] if len(flat) == 1 else ("alt", *flat)


def _inter(a: Expr, b: Expr) -> Expr:
    if _EMPTY_RE in (a, b):
        return _EMPTY_RE
    if b == _ANY_STAR:
        return a
    if a == _ANY_STAR:
        return b
    return ("inter", a, b)


def _loop(r: Expr, lo: int, hi: int | None) -> Expr:
    if hi == 0 or r == _EPS:
        return _EPS
    if r == _EMPTY_RE:
        return _EPS if lo == 0 else _EMPTY_RE
    if lo == hi == 1:
        return r
    return ("loop", r, lo, hi)


def _nullable(r: Expr) -> bool:
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


def _re_sets(r: Expr, out: set[Ranges]) -> set[Ranges]:
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


def to_node(r: Expr) -> Node:
    """Intent:
        Returns the expression `r` as a term node in canonical form.
    """
    return canonical(_to_node(r))


def _to_node(r: Expr) -> Node:
    kind = r[0]
    if kind == "eps":
        return {"op": "epsilon"}
    if kind == "empty":
        return {"op": "empty"}
    if kind == "chars":
        return {"op": "chars", "ranges": [[lo, hi] for lo, hi in r[1]]}
    if kind in ("cat", "alt", "inter"):
        op = {"cat": "concat", "alt": "union", "inter": "inter"}[kind]
        return {"op": op, "args": [_to_node(p) for p in r[1:]]}
    if kind == "not":
        return {"op": "complement", "arg": _to_node(r[1])}
    return {"op": "repeat", "arg": _to_node(r[1]), "min": r[2], "max": r[3]}


def from_node(node: Node) -> Expr:
    """Intent:
        Returns the expression a term node states.

    Raises:
        ValueError: the node is not one of the term's forms (see `canonical`).
    """
    node = canonical(node)
    op = node["op"]
    if op == "epsilon":
        return _EPS
    if op == "empty":
        return _EMPTY_RE
    if op == "literal":
        return _cat(*[("chars", ((c, c),)) for c in node["codes"]])
    if op == "chars":
        return ("chars", tuple((lo, hi) for lo, hi in node["ranges"]))
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
    return _loop(from_node(node["arg"]), node["min"], node["max"])


#: the language of every string, which an intersection drops
_EVERY_STRING = {"op": "repeat", "arg": {"op": "chars", "ranges": [[0, _MAX_CODE]]},
                 "min": 0, "max": None}


def _code(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= _MAX_CODE:
        raise ValueError(f"not a code point: {value!r}")
    return value


def _ranges(spans: Any) -> list[list[int]]:
    """Intent:
        Returns code point ranges sorted, with overlapping and adjacent ones merged.

    Raises:
        ValueError: a range is not two code points in order.
    """
    if not isinstance(spans, list):
        raise ValueError(f"not a list of ranges: {spans!r}")
    for span in spans:
        if not isinstance(span, list) or len(span) != 2 or _code(span[0]) > _code(span[1]):
            raise ValueError(f"not a range of code points: {span!r}")
    return [[lo, hi] for lo, hi in _cs_union(tuple((lo, hi) for lo, hi in spans))]


def _text(node: Node) -> str:
    """The serialisation the hash reads and arguments are ordered by."""
    import json
    return json.dumps(node, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def canonical(node: Node) -> Node:
    """Intent:
        Returns a term node in canonical form, by these rules, each applied to a node whose
        arguments are already canonical:

        1. `chars`: ranges sorted, overlapping and adjacent ones merged; no range is `empty`;
           one range of one code point is a `literal` of that code point.
        2. `literal`: `codes` is a list of code points; none is `epsilon`.
        3. `concat`: nested `concat` flattened; `epsilon` arguments dropped; with an `empty`
           argument it is `empty`; neighbouring `literal` arguments joined into one; no
           argument left is `epsilon`, one is that argument.
        4. `union`: nested `union` flattened; `empty` arguments dropped; equal arguments kept
           once; arguments sorted by their serialisation; none left is `empty`, one is that
           argument.
        5. `inter`: nested `inter` flattened; with an `empty` argument it is `empty`; the
           language of every string (a `repeat` from 0 with no maximum of the `chars` of all
           code points) dropped; equal arguments kept once; arguments sorted by their
           serialisation; none left is the language of every string, one is that argument.
        6. `repeat`: `max` 0, or an `epsilon` argument, is `epsilon`; an `empty` argument is
           `epsilon` when `min` is 0 and `empty` otherwise; `min` and `max` both 1 is the
           argument.
        7. `complement`, `epsilon` and `empty` are kept as they are.

        A node carries exactly the keys of its form. The serialisation is JSON with sorted
        keys, no white space and ASCII only; text is carried as code points, so it is one to
        one.

    Raises:
        ValueError: the node is not one of the forms, a code point is not an integer from 0
            to 0x10FFFF, a range is out of order, or a repeat's `min` is negative or above
            its `max`.
    """
    if not isinstance(node, dict):
        raise ValueError(f"not a term node: {node!r}")
    op = node.get("op")
    keys = {"empty": set(), "epsilon": set(), "literal": {"codes"}, "chars": {"ranges"},
            "concat": {"args"}, "union": {"args"}, "inter": {"args"}, "complement": {"arg"},
            "repeat": {"arg", "min", "max"}}
    if op not in keys or set(node) != keys[op] | {"op"}:
        raise ValueError(f"not a term node: {node!r}")
    if op in ("empty", "epsilon"):
        return {"op": op}
    if op == "literal":
        if not isinstance(node["codes"], list):
            raise ValueError(f"not a list of code points: {node['codes']!r}")
        codes = [_code(c) for c in node["codes"]]
        return {"op": "literal", "codes": codes} if codes else {"op": "epsilon"}
    if op == "chars":
        spans = _ranges(node["ranges"])
        if not spans:
            return {"op": "empty"}
        if len(spans) == 1 and spans[0][0] == spans[0][1]:
            return {"op": "literal", "codes": [spans[0][0]]}
        return {"op": "chars", "ranges": spans}
    if op == "complement":
        return {"op": "complement", "arg": canonical(node["arg"])}
    if op == "repeat":
        arg, lo, hi = canonical(node["arg"]), node["min"], node["max"]
        for bound in (lo, hi):
            if bound is not None and (isinstance(bound, bool) or not isinstance(bound, int)
                                      or bound < 0):
                raise ValueError(f"not a repeat count: {bound!r}")
        if lo is None or (hi is not None and hi < lo):
            raise ValueError(f"a repeat from {lo!r} to {hi!r}")
        if hi == 0 or arg == {"op": "epsilon"}:
            return {"op": "epsilon"}
        if arg == {"op": "empty"}:
            return {"op": "epsilon"} if lo == 0 else {"op": "empty"}
        if lo == hi == 1:
            return arg
        return {"op": "repeat", "arg": arg, "min": lo, "max": hi}
    if not isinstance(node["args"], list):
        raise ValueError(f"not a list of nodes: {node['args']!r}")
    args: list[Node] = []
    for arg in map(canonical, node["args"]):
        args.extend(arg["args"] if arg["op"] == op else [arg])
    if op == "concat":
        if {"op": "empty"} in args:
            return {"op": "empty"}
        joined: list[Node] = []
        for arg in args:
            if arg["op"] == "epsilon":
                continue
            if arg["op"] == "literal" and joined and joined[-1]["op"] == "literal":
                joined[-1] = {"op": "literal", "codes": joined[-1]["codes"] + arg["codes"]}
            else:
                joined.append(arg)
        none: Node = {"op": "epsilon"}
    else:
        if op == "inter" and {"op": "empty"} in args:
            return {"op": "empty"}
        drop = {"op": "empty"} if op == "union" else _EVERY_STRING
        by_text = {_text(arg): arg for arg in args if arg != drop}
        joined = [by_text[key] for key in sorted(by_text)]
        none = drop
    if not joined:
        return dict(none)
    return joined[0] if len(joined) == 1 else {"op": op, "args": joined}


def term_hash(doc: Node) -> str:
    """Intent:
        Returns the SHA-256 of a term's meaning: its version, alphabet, whether it is exact,
        and its language or its two bounds, each node in canonical form and the alphabet's
        ranges merged, serialised as `canonical` states. Its `kind` and `source` are not read,
        so a term compiled again to the same language hashes the same.

    Raises:
        ValueError: a node or the alphabet is not well formed.
    """
    import hashlib
    return hashlib.sha256(canonical_text(doc).encode("ascii")).hexdigest()


def _meaning(doc: Node) -> tuple[int, list[list[int]], bool, list[str]]:
    """Intent:
        Returns what a term states, checked: its version, its alphabet as merged ranges,
        whether it is exact, and the keys of the nodes it carries (`language`, or `at_least`
        and `at_most`).

    Raises:
        ValueError: the term is not an object, its version is not a whole number, it has no
            alphabet, its `exact` is not true or false, or an exact term lacks `language` or
            one that is not exact lacks a bound.
    """
    if not isinstance(doc, dict):
        raise ValueError(f"not a term: {doc!r}")
    version = doc.get("version")
    if isinstance(version, bool) or not isinstance(version, int):
        raise ValueError(f"a term's version is a whole number, not {version!r}")
    if "alphabet" not in doc:
        raise ValueError("a term states its alphabet")
    exact = doc.get("exact")
    stated = ((exact is True and "language" in doc)
              or (exact is False and "at_least" in doc and "at_most" in doc))
    if not stated:
        raise ValueError("an exact term (`exact` true) states `language`; one that is not "
                         "exact (`exact` false) states `at_least` and `at_most`")
    return (version, _ranges(doc["alphabet"]), exact is True,
            [key for key in ("language", "at_least", "at_most") if key in doc])


def canonical_text(doc: Node) -> str:
    """Intent:
        Returns the text `term_hash` hashes: the JSON object of `version`, `alphabet`, `exact`
        and `language` (or `at_least` and `at_most`), keys sorted, no white space.

    Raises:
        ValueError: the term or one of its nodes is not well formed.
    """
    version, alphabet, exact, keys = _meaning(doc)
    meaning: dict[str, Any] = {"version": version, "alphabet": alphabet, "exact": exact}
    for key in keys:
        meaning[key] = canonical(doc[key])
    return _text(meaning)


_DERIVATIVES: dict[tuple[Expr, int], Expr] = {}


def _derivative(r: Expr, code: int) -> Expr:
    """Intent:
        Returns the strings `w` with the character `code` followed by `w` in `r`.
    """
    key = (r, code)
    if key in _DERIVATIVES:
        return _DERIVATIVES[key]
    kind = r[0]
    out: Expr
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


def holds(r: Expr, text: str) -> bool:
    """Intent:
        Returns whether `text` is in the expression `r`: whether reading `r` from the start of
        `text` can end at its end, by the sets of positions each part can end at from each
        position it can start at. A repeat is read count by count until its count is reached
        and no new position is found, so a nested count takes time in the length of the text
        and the size of the expression, never in the number of ways to divide the text.
    """
    codes = [ord(c) for c in text]
    return len(codes) in _ends_from(r, 0, codes, {})


def _ends_from(r: Expr, start: int, codes: list[int], memo: dict[tuple[int, int], frozenset[int]]
               ) -> frozenset[int]:
    """Intent:
        Returns the positions of `codes` at which reading `r` from `start` can end.
    """
    key = (id(r), start)
    found = memo.get(key)
    if found is not None:
        return found
    kind = r[0]
    out: frozenset[int]
    if kind == "eps":
        out = frozenset((start,))
    elif kind == "empty":
        out = frozenset()
    elif kind == "chars":
        out = frozenset((start + 1,)) if start < len(codes) and _cs_has(r[1], codes[start]) else frozenset()
    elif kind == "cat":
        now = frozenset((start,))
        for part in r[1:]:
            now = frozenset().union(*(_ends_from(part, p, codes, memo) for p in now))
            if not now:
                break
        out = now
    elif kind == "alt":
        out = frozenset().union(*(_ends_from(p, start, codes, memo) for p in r[1:]))
    elif kind == "inter":
        out = _ends_from(r[1], start, codes, memo) & _ends_from(r[2], start, codes, memo)
    elif kind == "not":
        out = frozenset(range(start, len(codes) + 1)) - _ends_from(r[1], start, codes, memo)
    else:
        out = _repeat_ends(r[1], r[2], r[3], start, codes, memo)
    memo[key] = out
    return out


def _repeat_ends(sub: Expr, lo: int, hi: int | None, start: int, codes: list[int],
                 memo: dict[tuple[int, int], frozenset[int]]) -> frozenset[int]:
    """Intent:
        Returns the positions at which `lo` to `hi` readings of `sub` in a row can end, from
        `start`: the positions after exactly k readings, for k counted up to `lo` (stopping
        early once they stop changing, since every later count then gives the same), then
        every position reached after more readings, up to `hi`, until no new one is found.
    """
    def step(at: frozenset[int]) -> frozenset[int]:
        return frozenset().union(*(_ends_from(sub, p, codes, memo) for p in at))

    exact, taken = frozenset((start,)), 0
    while taken < lo and exact:
        after = step(exact)
        taken += 1
        if after == exact:
            taken = lo
        exact = after
    reached, frontier = set(exact), exact
    while frontier and (hi is None or taken < hi):
        frontier = step(frontier) - reached
        reached |= frontier
        taken += 1
    return frozenset(reached)


def member(doc: Node, text: str, bound: str = "language") -> bool:
    """Intent:
        Returns whether `text` is in a term's language, or in its `at_least` or `at_most` bound
        (an exact term's language is both), read by its UTF-16 code units when the term's
        alphabet is the code units. The language is over the term's alphabet: a text with a
        character outside it is no member, and a complement is the strings over the alphabet
        outside its argument.

    Raises:
        ValueError: the alphabet is not well formed, or the term is not exact and `bound`
            names neither bound.

    Notes:
        A term that states no alphabet is read over every code point.
    """
    alphabet = _ranges(doc["alphabet"]) if "alphabet" in doc else [[0, _MAX_CODE]]
    if "language" not in doc and bound not in ("at_least", "at_most"):
        raise ValueError("the term is not exact: ask for its at_least or its at_most bound")
    if alphabet == [[0, 0xFFFF]]:
        text = code_units(text)
    if alphabet != [[0, _MAX_CODE]] and not all(_cs_has(alphabet, ord(c)) for c in text):
        return False
    node = doc["language"] if "language" in doc else doc[bound]
    kept = _READ.get(id(node))
    if kept is None or kept[0] is not node:
        if len(_READ) > 256:
            _READ.clear()
        kept = _READ[id(node)] = (node, from_node(node))
    return holds(kept[1], text)


#: the expression of each node `member` has read, kept with the node it was read from
_READ: dict[int, tuple[Node, Expr]] = {}


def code_units(text: str) -> str:
    """Intent:
        Returns `text` as its UTF-16 code units, one character each: a character past U+FFFF
        becomes its two surrogates.
    """
    out = []
    for c in text:
        code = ord(c)
        if code > 0xFFFF:
            code -= 0x10000
            out.append(chr(0xD800 + (code >> 10)) + chr(0xDC00 + (code & 0x3FF)))
        else:
            out.append(c)
    return "".join(out)


def code_points(text: str) -> str:
    """Intent:
        Returns `text` with each high surrogate followed by a low one read as the one character
        the pair encodes, as a reader of UTF-16 by code points reads it.
    """
    return re.sub("[\ud800-\udbff][\udc00-\udfff]",
                  lambda m: chr(0x10000 + ((ord(m[0][0]) - 0xD800) << 10) + ord(m[0][1]) - 0xDC00),
                  text)


def shortest(r: Expr, limit: int = 12) -> str | None:
    """Intent:
        Returns a shortest string in the expression `r` of at most `limit` characters, found
        breadth first over derivatives, or None when there is none that short.

    Notes:
        The characters tried are the first of each interval of every set `r` names, so the
        search can miss a member that needs some other character: it finds examples, and its
        None is not a proof of emptiness.
    """
    chars = sorted({lo for s in _re_sets(r, set()) for lo, _ in s})
    frontier = [("", r)]
    seen = {r}
    for _ in range(limit + 1):
        nxt = []
        for text, state in frontier:
            if _nullable(state):
                return text
            for code in chars:
                d = _derivative(state, code)
                if d != _EMPTY_RE and d not in seen:
                    seen.add(d)
                    nxt.append((text + chr(code), d))
        frontier = nxt
        if not frontier:
            return None
    return None


def every_string_over(chars: Any, name: str) -> Node:
    """Intent:
        Returns the term of every string over the code points `chars` (sorted disjoint
        ranges), the empty string included, for the alphabet language `name`.
    """
    node = {"op": "repeat", "arg": {"op": "chars", "ranges": [[lo, hi] for lo, hi in chars]},
            "min": 0, "max": None}
    return {"kind": "regular_language", "version": TERM_VERSION, "alphabet": [[0, _MAX_CODE]],
            "exact": True, "language": canonical(node), "source": {"alphabet": name}}


def of_length(doc: Node, lo: int, hi: int | None) -> Node:
    """Intent:
        Returns the term of the strings of `doc` whose length in characters of its alphabet is
        `lo` to `hi` (`None`: unbounded): each language or bound of `doc` met with the strings
        of that length, and a repeat of single characters from zero read as that repeat with
        the new counts.
    """
    every = {"op": "chars", "ranges": doc["alphabet"]}

    def cut(node: Node) -> Node:
        node = canonical(node)
        one_character = node.get("arg", {}).get("op") in ("chars", "literal") and (
            node["arg"]["op"] == "chars" or len(node["arg"]["codes"]) == 1)
        if node["op"] == "repeat" and node["min"] == 0 and node["max"] is None and one_character:
            return canonical({"op": "repeat", "arg": node["arg"], "min": lo, "max": hi})
        return canonical({"op": "inter", "args": [
            node, {"op": "repeat", "arg": every, "min": lo, "max": hi}]})

    out = {**doc, "source": {**doc.get("source", {}), "length": [lo, hi]}}
    for key in ("language", "at_least", "at_most"):
        if key in doc:
            out[key] = cut(doc[key])
    return out
