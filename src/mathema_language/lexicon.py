# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Worked claims over this package's languages, the examples the docs
draw from and the tests check: each parses, its language resolves,
and it adjudicates against the function beside it. mathema's own
lexicon holds the grammar; this one holds the claims a parser, a
renderer, a normaliser or a validator earns over a language."""
from __future__ import annotations

LEXICON: dict[str, str] = {
    # a union with a finite set: the sentinel a field uses beside the
    # language proper
    "language_with_special_member":
        'for text in L[alnum] | {"n/a"}, len(f(text)) <= len(text)',
    # a parser of decimal digits is a homomorphism from concatenation
    # to arithmetic
    "language_homomorphism":
        'for s in L[digit] \\ {""}, f(s + "0") == 10 * f(s)',
    # an encoding boundary: the function is falsified with the member
    # past the boundary as the witness
    "language_encoding_boundary": "for text in L[latin-1], f(text) == text",
    # a section: the inverse, bound with let, undoes the function
    "language_section":
        "let u = mathema_language.lexicon.unescape_angle, "
        "for text in L[unicode], u(f(text)) == text",
    # a retraction on a predicate language: parse, render, parse again
    "language_retraction":
        "let dump = json.dumps, for s in L[json], f(dump(f(s))) == f(s)",
    # a normaliser is idempotent over every string
    "language_idempotent": "for text in L[unicode], f(f(text)) == f(text)",
}


def collapse_spaces(text: str) -> str:
    """Runs of whitespace collapsed to one space, the ends stripped."""
    return " ".join(text.split())


def escape_angle(text: str) -> str:
    """Angle brackets and ampersands written as their entities."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def unescape_angle(text: str) -> str:
    """The inverse of `escape_angle` on its image."""
    return text.replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&")


def digits_to_int(s: str) -> int:
    """The integer a string of decimal digits spells."""
    return int(s)


def ascii_only(text: str) -> str:
    """The text, if ascii; a UnicodeEncodeError otherwise."""
    return text.encode("ascii").decode("ascii")


def loads(s: str) -> object:
    """The value a JSON document spells."""
    import json
    return json.loads(s)


#: which function each lexicon key is checked against
EXAMPLE_FUNCTIONS: dict[str, tuple[object, list[str]]] = {
    "collapse_spaces": (collapse_spaces, ["language_with_special_member",
                                          "language_idempotent"]),
    "digits_to_int": (digits_to_int, ["language_homomorphism"]),
    "ascii_only": (ascii_only, ["language_encoding_boundary"]),
    "escape_angle": (escape_angle, ["language_section"]),
    "loads": (loads, ["language_retraction"]),
}

__all__ = ["EXAMPLE_FUNCTIONS", "LEXICON", "ascii_only", "collapse_spaces",
           "digits_to_int", "escape_angle", "loads", "unescape_angle"]
