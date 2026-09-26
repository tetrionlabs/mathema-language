# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Members of a regular expression, drawn from its parse tree:
literals, classes and ranges, the `\\d` `\\w` `\\s` categories and
their negations, alternation, groups, back-references and bounded
or unbounded repeats (an unbounded repeat draws a few). Anchors and
look-arounds contribute nothing; a pattern with a construct this
module does not read raises, and the caller falls back to
rejection."""
from __future__ import annotations

import importlib
import random
import re
import string
from typing import Any

try:
    _sre: Any = importlib.import_module("re._parser")
except ImportError:  # pragma: no cover
    _sre = importlib.import_module("sre_parse")

_MAX_UNBOUNDED = 4
_WORD = string.ascii_letters + string.digits + "_"
_DIGIT = string.digits
_SPACE = " \t\n\r\x0b\x0c"
_ANY = string.ascii_letters + string.digits + " _-.,:;!?@#/" + "éß漢字"


class Unsupported(ValueError):
    """The pattern uses a construct this generator does not read."""


def _category(code: Any, negate: bool) -> str:
    name = str(code).rsplit("_", 1)[-1].lower()
    pool = {"digit": _DIGIT, "word": _WORD, "space": _SPACE}.get(name)
    if pool is None:
        raise Unsupported(f"category {code}")
    if negate:
        return "".join(c for c in _ANY if c not in pool) or "x"
    return pool


def _class_pool(items: list[tuple[Any, Any]]) -> str:
    pool = ""
    negate = False
    for op, arg in items:
        name = str(op).rsplit(".", 1)[-1]
        if name == "NEGATE":
            negate = True
        elif name == "LITERAL":
            pool += chr(arg)
        elif name == "RANGE":
            lo, hi = arg
            pool += "".join(chr(c) for c in range(lo, min(hi, lo + 200) + 1))
        elif name == "CATEGORY":
            pool += _category(arg, False)
        else:
            raise Unsupported(f"class item {name}")
    if negate:
        pool = "".join(c for c in _ANY if c not in pool) or "x"
    return pool or "x"


def _emit(rng: random.Random, items: Any, groups: dict[int, str]) -> str:
    out = ""
    for op, arg in items:
        name = str(op).rsplit(".", 1)[-1]
        if name == "LITERAL":
            out += chr(arg)
        elif name == "NOT_LITERAL":
            out += rng.choice([c for c in _ANY if c != chr(arg)])
        elif name == "ANY":
            out += rng.choice(_ANY)
        elif name == "IN":
            out += rng.choice(_class_pool(arg))
        elif name == "CATEGORY":
            out += rng.choice(_category(arg, False))
        elif name == "AT":
            continue
        elif name == "BRANCH":
            _, branches = arg
            out += _emit(rng, rng.choice(branches), groups)
        elif name == "SUBPATTERN":
            group, _, _, sub = arg
            text = _emit(rng, sub, groups)
            if group is not None:
                groups[group] = text
            out += text
        elif name in ("MAX_REPEAT", "MIN_REPEAT", "POSSESSIVE_REPEAT"):
            lo, hi, sub = arg
            top = hi if hi is not _sre.MAXREPEAT and hi < lo + _MAX_UNBOUNDED else lo + _MAX_UNBOUNDED
            for _ in range(rng.randint(lo, top)):
                out += _emit(rng, sub, groups)
        elif name == "GROUPREF":
            out += groups.get(arg, "")
        elif name == "ATOMIC_GROUP":
            out += _emit(rng, arg, groups)
        else:
            raise Unsupported(name)
    return out


def draw_matching(rng: random.Random, pattern: str, tries: int = 20) -> str | None:
    """One string `re.fullmatch(pattern, s)` accepts, or None when
    the pattern uses a construct this module does not read or no
    draw matched."""
    try:
        parsed = _sre.parse(pattern)
    except Exception:
        return None
    for _ in range(tries):
        try:
            s = _emit(rng, parsed, {})
        except Unsupported:
            return None
        if re.fullmatch(pattern, s) is not None:
            return s
    return None


__all__ = ["Unsupported", "draw_matching"]
