# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Finite sets of words as regular expressions.

`finite_pattern` writes the expression that, read in full, admits
exactly the given words; `finite_complement` the one that admits every
word over an alphabet except the given ones. Both walk the words as a
trie in which first characters leading to the same set of remainders
share one character class, so a run of numbers (`0` to `255`, the leap
years of a century) comes out as the usual digit-by-digit expression.
The expressions use literals, character classes, groups, alternation
and `?` only.
"""
from __future__ import annotations

import re
from collections.abc import Iterable


def _class(chars: Iterable[str], negate: bool = False) -> str:
    """Intent:
        The character class of exactly `chars` (of every other character with `negate`), runs of
        consecutive code points written as ranges; one character alone is written as a literal.

    Raises:
        ValueError: `chars` is empty.
    """
    codes = sorted({ord(c) for c in chars})
    if not codes:
        raise ValueError("a character class holds at least one character")
    if len(codes) == 1 and not negate:
        return re.escape(chr(codes[0]))
    runs: list[list[int]] = []
    for code in codes:
        if runs and code == runs[-1][1] + 1:
            runs[-1][1] = code
        else:
            runs.append([code, code])

    def one(code: int) -> str:
        ch = chr(code)
        return "\\" + ch if ch in "\\]^-[" else (ch if ch.isprintable() and ch != " " else f"\\x{code:02x}"
                                                  if code < 256 else f"\\u{code:04x}" if code < 65536
                                                  else f"\\U{code:08x}")

    body = "".join(one(a) if a == b else one(a) + one(b) if b == a + 1 else one(a) + "-" + one(b)
                   for a, b in runs)
    return ("[^" if negate else "[") + body + "]"


def _heads(words: frozenset[str], fold: bool) -> dict[frozenset[str], set[str]]:
    """Intent:
        The first characters of the non-empty `words`, grouped by the set of remainders that
        follow them. With `fold`, a letter stands for both of its cases.
    """
    tails: dict[str, set[str]] = {}
    for word in words:
        if word:
            tails.setdefault(word[0], set()).add(word[1:])
    groups: dict[frozenset[str], set[str]] = {}
    for head, rest in tails.items():
        heads = groups.setdefault(frozenset(rest), set())
        heads.update({head.lower(), head.upper()} if fold else {head})
    return groups


def finite_pattern(words: Iterable[str], fold: bool = False) -> str:
    """Intent:
        The regular expression that, read in full, admits exactly `words`. With `fold`, the
        words are given in one case and each letter is admitted in both.

    Raises:
        ValueError: `words` is empty.

    Notes:
        The result is one alternative: it can be followed or preceded by more of an expression,
        and needs a group before a repeat or inside an alternation.
    """
    memo: dict[frozenset[str], str] = {}

    def build(ws: frozenset[str]) -> str:
        if ws in memo:
            return memo[ws]
        alternatives = sorted(_class(heads) + build(rest) for rest, heads in _heads(ws, fold).items())
        body = "" if not alternatives else (
            alternatives[0] if len(alternatives) == 1 else "(?:" + "|".join(alternatives) + ")")
        if "" in ws and body:
            body = "(?:" + body + ")?"
        memo[ws] = body
        return body

    given = frozenset(words)
    if not given:
        raise ValueError("a finite pattern admits at least one word")
    return build(given)


def finite_complement(words: Iterable[str], excluded: str) -> str:
    """Intent:
        The regular expression that, read in full, admits every word over the alphabet except
        `words`, the empty word included when it is not one of them. The alphabet is every
        character not in `excluded`.

    Raises:
        ValueError: `excluded` is empty, or a word uses a character in `excluded`.

    Notes:
        The result is a group, safe to repeat or to place in an alternation.
    """
    if not excluded:
        raise ValueError("the alphabet excludes at least one character")
    given = frozenset(words)
    if any(c in excluded for word in given for c in word):
        raise ValueError("a word outside the alphabet is already excluded")
    anything = _class(excluded, negate=True) + "*"

    def build(ws: frozenset[str]) -> str:
        if not ws:
            return anything
        tails: dict[str, set[str]] = {}
        for word in ws:
            if word:
                tails.setdefault(word[0], set()).add(word[1:])
        alternatives = [_class(excluded + "".join(tails), negate=True) + anything]
        alternatives += [re.escape(head) + build(frozenset(rest)) for head, rest in sorted(tails.items())]
        if "" not in ws:
            alternatives.append("")
        return "(?:" + "|".join(alternatives) + ")"

    return build(given)


__all__ = ["finite_complement", "finite_pattern"]
