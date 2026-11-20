# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A regular-language term read out in plain words.

`explain(term)` says what text a term admits, in the order the text is
read: `^[a-z0-9]+(?:-[a-z0-9]+)*$` under `starts with` reads

    one or more of: 0-9, a-z; then any number of: "-" followed by one or
    more of: 0-9, a-z; also accepts one final newline

The reading is of the term alone, in canonical form, so two terms with
one canonical form read the same whatever pattern they came from.

- Parts in sequence are joined by `; then` at the top and by
  `followed by` inside a repeat or a choice; there, a part with its
  own list or repeat is bracketed unless it comes last, and deeper
  sequences are bracketed whole. One character set written several
  times in a row reads as that many of it.
- A repeat reads by its count: `optionally`, `any number of`, `one or
  more of`, `exactly 3 of`, `2 to 4 of`, `up to 4 of`, `2 or more of`.
- A choice between literal texts reads `one of: "a", "b"`; any other
  choice `either ... or ...`. The literal texts come first, in code
  point order, then the other alternatives in the canonical form's
  order.
- A character set reads as its ranges in code point order (`0-9, a-z`),
  a single character in quotes or by name (`space`, `newline`, `tab`),
  with its code point after it outside ASCII and alone when it does not
  print,
  and by a class name where it equals one: `any character`, `letters`
  (what `str.isalpha` accepts), `digits` (what `\\d` matches),
  `whitespace` (what `\\s` matches), `word characters` (what `\\w`
  matches), each over Unicode with its size, or `ASCII letters`. A set
  that holds one of those classes names it and lists the rest; a set
  the caller names (a shape's bound alphabet) reads by that name; a set
  easier to say by what it leaves out reads `any character except: ...`.
  A long list is cut after eight parts, with the number of characters
  left unsaid.
- Text that may end in one newline, as `$` allows, reads `also accepts
  one final newline`.

A term that is not exact is read as what it is, a pair of bounds:
the reading names the constructs that made it approximate (the source's
`not_exact` list), then reads `at_least`, which every accepted text
fits, and `at_most`, the texts certainly accepted. A cause that ends
`between Python versions` is a character class that is not one set on
every supported Python, and reads `approximate because it holds
letters, which differ slightly between Python versions`.
"""
from __future__ import annotations

import contextvars
import functools
import json
from typing import Any

from . import _regular

Ranges = tuple[tuple[int, int], ...]

#: the most parts a character set lists before the rest is counted
_MAX_PARTS = 8

#: the names a reading gives to whole character sets, by their ranges, while it runs
_NAMES: contextvars.ContextVar[dict[Ranges, str]] = contextvars.ContextVar("set names", default={})  # noqa: B039

#: how a cause in a term's `not_exact` list ends when the term is a bound because a Unicode
#: class is not the same set on every supported Python
_BETWEEN_VERSIONS = "between Python versions"

_NAMED_CHARACTERS = {" ": "space", "\n": "newline", "\t": "tab", "\r": "carriage return"}


def _size(ranges: Ranges) -> int:
    """Intent:
        The number of code points in the ranges.
    """
    return sum(hi - lo + 1 for lo, hi in ranges)


#: the version table's classes a reading names, with their names
_CLASS_NAMES = (("word", "word characters"), ("unicode_alpha", "letters"),
                ("lowercase_letter", "lower-case letters"), ("space", "whitespace"),
                ("decimal", "digits"))


@functools.lru_cache(maxsize=1)
def _classes() -> tuple[tuple[str, Ranges], ...]:
    """Intent:
        The named Unicode classes as a term may hold them, largest first, each with the words
        that say it: word characters (`\\w`), letters (`str.isalpha` of one character),
        lower-case letters, whitespace (`\\s`) and digits (`\\d`), as one supported Python
        reads the class, as every supported Python does, and as any may.
    """
    data = _regular.versions_data()
    found: dict[Ranges, str] = {}
    for key, name in _CLASS_NAMES:
        entry = data["classes"][key]
        low, high = (tuple(r) for r in _regular.class_bounds(key))
        for members in entry["by_version"].values():
            found.setdefault(tuple(members), f"{name} (Unicode, {_size(tuple(members))} characters)")
        if low != high:
            found.setdefault(
                low, f"{name} (Unicode, the {_size(low)} characters every supported Python holds)")
            found[high] = f"{name} (Unicode, every character a supported Python holds or may come to)"
    return tuple(sorted(((said, members) for members, said in found.items()),
                        key=lambda pair: -_size(pair[1])))


def _one(code: int) -> str:
    """Intent:
        One code point as a set lists it: by name for a space, newline, tab or carriage return,
        in double quotes when it prints, with `U+` and its number after it outside ASCII, and
        as `U+` and its number alone when it does not print.
    """
    ch = chr(code)
    if ch in _NAMED_CHARACTERS:
        return _NAMED_CHARACTERS[ch]
    if ch.isprintable() and code < 128:
        return json.dumps(ch)
    if ch.isprintable():
        return f"{json.dumps(ch, ensure_ascii=False)} (U+{code:04X})"
    return f"U+{code:04X}"


def _listed(ranges: Ranges) -> str:
    """Intent:
        The ranges as a list in code point order, cut after `_MAX_PARTS` ranges with the number
        of characters left unsaid: a range between ASCII letters or digits as `a-z`, any other
        as its two ends joined by `to`, two neighbours as two characters.
    """
    parts = []
    for lo, hi in ranges[:_MAX_PARTS]:
        if lo == hi:
            parts.append(_one(lo))
        elif hi == lo + 1:
            parts += [_one(lo), _one(hi)]
        elif all(c < 128 and chr(c).isalnum() for c in (lo, hi)):
            parts.append(f"{chr(lo)}-{chr(hi)}")
        else:
            parts.append(f"{_one(lo)} to {_one(hi)}")
    left = _size(ranges[_MAX_PARTS:])
    if left:
        parts.append(f"{left} more characters")
    return ", ".join(parts)


def _minus(a: Ranges, b: Ranges) -> Ranges:
    """Intent:
        The code points of `a` that are not in `b`.
    """
    return tuple(_regular._cs_inter(a, _regular._cs_complement(b)))


def _contained(ranges: Ranges) -> str:
    """Intent:
        A set that is not everything, said by what it holds: the named Unicode classes inside
        it, largest first and each with its size, then the rest as a list; `ASCII letters` and
        `no character` where it is exactly those.
    """
    if not ranges:
        return "no character"
    if ranges == ((65, 90), (97, 122)):
        return "ASCII letters"
    names = []
    rest = ranges
    for said, members in _classes():
        if tuple(_regular._cs_inter(rest, members)) == members:
            names.append(said)
            rest = _minus(rest, members)
    return ", ".join(names + ([_listed(rest)] if rest else []))


def describe_characters(ranges: Any) -> str:
    """Intent:
        Returns a character set in words: `any character`, the classes and ranges it holds, or,
        when what it leaves out is shorter to say and the set is most of Unicode,
        `any character except: ...`.

    Notes:
        `ranges` are inclusive code point pairs; they are sorted and merged before reading, so
        one set reads one way however it is written.
    """
    given = tuple(_regular._cs_union(*[((int(lo), int(hi)),) for lo, hi in ranges]))
    if given in _NAMES.get():
        return _NAMES.get()[given]
    if given == _regular._FULL:
        return "any character"
    for said, members in _classes():
        if given == members:
            return said
    left_out = tuple(_regular._cs_complement(given))
    if _size(given) > _size(left_out):
        return "any character except: " + _contained(left_out)
    return _contained(given)


def _count(lo: int, hi: int | None) -> str:
    """Intent:
        The words for a repeat from `lo` to `hi` times, `hi` None for no upper bound.
    """
    if hi is None:
        return "any number of" if lo == 0 else "one or more of" if lo == 1 else f"{lo} or more of"
    if (lo, hi) == (0, 1):
        return "optionally"
    if lo == hi:
        return f"exactly {lo} of"
    return f"up to {hi} of" if lo == 0 else f"{lo} to {hi} of"


def _is_final_newline(node: dict[str, Any]) -> bool:
    """Intent:
        Whether the node is an optional single newline: nothing or `"\\n"`.
    """
    newline = {"op": "literal", "codes": [10]}
    if node["op"] == "repeat":
        return node["arg"] == newline and (node["min"], node["max"]) == (0, 1)
    return node["op"] == "union" and len(node["args"]) == 2 and newline in node["args"] \
        and {"op": "epsilon"} in node["args"]


def _runs(args: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Intent:
        The parts of a sequence with each run of one character set, written out several times
        in a row, read as that set repeated exactly that many times.
    """
    out: list[dict[str, Any]] = []
    for arg in args:
        last = out[-1] if out else None
        if arg["op"] == "chars" and last is not None:
            if last == arg:
                out[-1] = {"op": "repeat", "arg": arg, "min": 2, "max": 2, "run": True}
                continue
            if last["op"] == "repeat" and last["arg"] == arg and last["min"] == last["max"] \
                    and last.get("run"):
                out[-1] = {**last, "min": last["min"] + 1, "max": last["max"] + 1}
                continue
        out.append(arg)
    return out


def _whole(said: str) -> bool:
    """Intent:
        Whether the words are one bracketed unit: they open with a round bracket whose own
        closing bracket is their last character. Brackets inside quoted text are not counted.
    """
    if not said.startswith("("):
        return False
    depth, quoted, skip = 0, False, False
    for at, ch in enumerate(said):
        if skip:
            skip = False
        elif quoted:
            skip, quoted = ch == "\\", ch != '"'
        elif ch == '"':
            quoted = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return at == len(said) - 1
    return False


def _simple(node: dict[str, Any]) -> bool:
    """Intent:
        Whether the node reads as one unit with no joining words: a literal, a character set,
        the empty text or the empty language.
    """
    return node["op"] in ("literal", "chars", "epsilon", "empty")


def _read(node: dict[str, Any], depth: int) -> str:
    """Intent:
        The node in words. `depth` is 0 for the whole term and grows by one inside each repeat
        or choice; it picks the words that join a sequence and whether it is bracketed.
    """
    op = node["op"]
    if op == "empty":
        return "nothing (no text is accepted)"
    if op == "epsilon":
        return "the empty text"
    if op == "literal":
        return json.dumps("".join(map(chr, node["codes"])), ensure_ascii=False)
    if op == "chars":
        said = describe_characters(node["ranges"])
        return said if said.startswith("any character") else "one of: " + said
    if op == "concat":
        args = list(node["args"])
        final = depth == 0 and len(args) > 1 and _is_final_newline(args[-1])
        if final:
            args.pop()
        args = _runs(args)
        if len(args) == 1:
            said = _read(args[0], depth)
        elif depth == 0:
            said = "; then ".join(_read(a, 0) for a in args)
        else:
            parts = [_inner(a, depth) for a in args]
            parts = [f"({p})" if ": " in p and not _whole(p) else p for p in parts[:-1]] + parts[-1:]
            said = " followed by ".join(parts)
            if depth >= 2:
                said = "(" + said + ")"
        return said + ("; also accepts one final newline" if final else "")
    if op == "repeat":
        arg, words = node["arg"], _count(node["min"], node["max"])
        if arg["op"] == "chars":
            said = describe_characters(arg["ranges"])
            if said == "any character" and node["max"] is None:
                return "any text" if node["min"] == 0 else f"any text of {node['min']} or more characters"
            return f"{words}: {said}" if words != "optionally" else f"optionally one of: {said}"
        return f"{words}: {_inner(arg, depth + 1)}" if words != "optionally" \
            else f"optionally: {_inner(arg, depth + 1)}"
    if op == "union":
        args = [a for a in node["args"] if a["op"] != "epsilon"]
        optional = len(args) < len(node["args"])
        args = (sorted((a for a in args if a["op"] == "literal"), key=lambda a: a["codes"])
                + [a for a in args if a["op"] != "literal"])
        if all(a["op"] == "literal" for a in args) and len(args) > 1:
            said = "one of: " + ", ".join(_read(a, depth + 1) for a in args)
        elif len(args) == 1:
            said = _inner(args[0], depth + 1)
        else:
            said = "either " + " or ".join(_bracketed(a, depth + 1) for a in args)
        return f"optionally: {said}" if optional else said
    if op == "inter":
        return "text that is all of: " + " and ".join(_bracketed(a, depth + 1) for a in node["args"])
    if op == "complement":
        return "any text except: " + _bracketed(node["arg"], depth + 1)
    raise ValueError(f"not a term node: {node!r}")


def _inner(node: dict[str, Any], depth: int) -> str:
    """Intent:
        The node in words as one part of a sequence or the operand of a repeat: a choice is
        bracketed, so the words around it cannot be read into it.
    """
    return _bracketed(node, depth) if node["op"] in ("union", "inter", "complement") else _read(node, depth)


def _bracketed(node: dict[str, Any], depth: int) -> str:
    """Intent:
        The node in words, in round brackets unless it reads as one unit.
    """
    said = _read(node, max(depth, 1))
    return said if _simple(node) or _whole(said) else "(" + said + ")"


def explain_node(node: dict[str, Any]) -> str:
    """Intent:
        Returns one term node in plain words, read in canonical form.

    Raises:
        ValueError: the node is not one of the term's forms.
    """
    return _read(_regular.canonical(node), 0)


def explain(term: dict[str, Any], names: Any = None) -> str:
    """Intent:
        Returns what text a regular-language term admits, in plain words. An exact term is
        read as fact. A term stated as bounds says so, names the constructs that made it
        approximate, and reads each bound for what it is: every accepted text fits `at_least`;
        every text in `at_most` is accepted.

    Raises:
        ValueError: the document is not a regular-language term.

    Notes:
        Only the term's meaning is read (`exact`, `language` or the two bounds) and, for
        bounds, the source's `not_exact` list. Terms with one canonical form read the same.
        `names` maps a character set, as a tuple of inclusive ranges, to the name the reading
        gives it in place of its ranges: a shape names the alphabets its symbols are bound to.
    """
    token = _NAMES.set({tuple(tuple(r) for r in ranges): str(name) for ranges, name in (names or {}).items()})
    try:
        return _explain(term)
    finally:
        _NAMES.reset(token)


def _explain(term: dict[str, Any]) -> str:
    """Intent:
        The reading of a term under the set names in force.

    Raises:
        ValueError: the document is not a regular-language term.
    """
    if not isinstance(term, dict) or term.get("kind") != "regular_language":
        raise ValueError("explain reads a regular-language term")
    if term.get("exact") and "language" in term:
        return explain_node(term["language"])
    if "at_least" not in term or "at_most" not in term:
        raise ValueError("a term states its language, or an at_least and an at_most bound")
    causes = list((term.get("source") or {}).get("not_exact") or [])
    versions = [c for c in causes if c.endswith(_BETWEEN_VERSIONS)]
    uses = [c for c in causes if not c.endswith(_BETWEEN_VERSIONS)]
    reasons = ([f"the pattern uses {_and(uses)}"] if uses else []) + (
        [f"it holds {_and(versions)}"] if versions else [])
    why = (" because " + " and ".join(reasons)) if reasons else ""
    most = _regular.canonical(term["at_most"])
    certain = ("no text is known to be accepted for certain" if most == {"op": "empty"}
               else "certainly accepted: " + _read(most, 0))
    return (f"approximate{why}; every accepted text fits: {explain_node(term['at_least'])}; "
            f"not every text that fits is accepted; {certain}")


def _reading(pattern: str, predicate: str) -> str:
    """Intent:
        The plain-words reading of a Python pattern under a predicate.

    Claims:
        a_set_reads_the_same_however_it_is_ordered: f("[a-z0-9]+", "matches") == f("[0-9a-z]+", "matches")
        a_count_reads_the_same_however_it_is_spelled: f("a{1,}", "matches") == f("a+", "matches")
        a_slug_reads_as_words_joined_by_hyphens: f("[a-z0-9]+(?:-[a-z0-9]+)*", "matches") == 'one or more of: 0-9, a-z; then any number of: "-" followed by one or more of: 0-9, a-z'
        a_dollar_reads_as_a_final_newline: f("a$", "starts with") == '"a"; also accepts one final newline'
        the_end_of_text_reads_as_no_newline: f("a\\Z", "starts with") == '"a"'

    Raises:
        NotRegular: the pattern does not compile.
        ValueError: the predicate is not one the term module reads.
    """
    return explain(_regular.term(pattern, 0, predicate))


def _and(parts: list[str]) -> str:
    """Intent:
        The parts as an English list ending in `and`.
    """
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


__all__ = ["describe_characters", "explain", "explain_node"]
