# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Worked claims over this package's languages, the examples the docs
draw from and the tests check: each parses, its language resolves,
and it adjudicates against the function beside it. mathema's own
lexicon holds the grammar; this one holds the claims a parser, a
renderer, a normaliser or a validator earns over a language.
Registered under `mathema.lexicon` as `language`, so with the package
installed these rows join mathema's own in `mathema.lexicon.entries()`,
`search()` and `find()`."""
from __future__ import annotations

LEXICON: dict[str, str] = {
    # a union with a finite set: the sentinel a field uses beside the
    # language proper
    "language_with_special_member":
        'for s in L[alnum] | {"n/a"}, len(f(s)) <= len(s)',
    # a parser of decimal digits is a homomorphism from concatenation
    # to arithmetic
    "language_homomorphism":
        'for s in L[digit] \\ {""}, f(s + "0") == 10 * f(s)',
    # an encoding boundary: the function is falsified with the member
    # past the boundary as the witness
    "language_encoding_boundary": "for s in L[latin-1], f(s) == s",
    # a section: the inverse, bound with let, undoes the function
    "language_section_inverse":
        "let u = mathema_language.lexicon.unescape_angle, "
        "for s in L[unicode], u(f(s)) == s",
    # a retraction on a predicate language: parse, render, parse again
    "language_retraction":
        "let dump = json.dumps, for s in L[json], f(dump(f(s))) == f(s)",
    # a normaliser is idempotent over every string
    "language_idempotent": "for s in L[unicode], f(f(s)) == f(s)",
}


def collapse_spaces(s: str) -> str:
    """Runs of whitespace collapsed to one space, the ends stripped."""
    return " ".join(s.split())


def escape_angle(s: str) -> str:
    """Angle brackets and ampersands written as their entities."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def unescape_angle(s: str) -> str:
    """The inverse of `escape_angle` on its image."""
    return s.replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&")


def digits_to_int(s: str) -> int:
    """The integer a string of decimal digits spells."""
    return int(s)


def ascii_only(s: str) -> str:
    """The s, if ascii; a UnicodeEncodeError otherwise."""
    return s.encode("ascii").decode("ascii")


def loads(s: str) -> object:
    """The value a JSON document spells."""
    import json
    return json.loads(s)


#: the lexicon's table of contents, every key in exactly one section;
#: installed, mathema reads these as `language/<section>`
SECTIONS: dict[str, tuple[str, ...]] = {
    "domains": ("language_with_special_member",),
    "laws": ("language_homomorphism", "language_section_inverse", "language_retraction",
             "language_idempotent"),
    "boundaries": ("language_encoding_boundary",),
}

#: everyday words each row is found by through `mathema.lexicon.find`
TAGS: dict[str, tuple[str, ...]] = {
    "language_with_special_member": ("sentinel", "placeholder value", "union with a set"),
    "language_homomorphism": ("homomorphism", "append a digit", "parse digits"),
    "language_encoding_boundary": ("encoding error", "codec", "latin-1"),
    "language_section_inverse": ("round trip", "inverse", "unescape"),
    "language_retraction": ("retraction", "parse render parse", "json round trip"),
    "language_idempotent": ("idempotent", "normaliser", "apply twice"),
}

#: which function each lexicon key is checked against
EXAMPLE_FUNCTIONS: dict[str, tuple[object, list[str]]] = {
    "collapse_spaces": (collapse_spaces, ["language_with_special_member",
                                          "language_idempotent"]),
    "digits_to_int": (digits_to_int, ["language_homomorphism"]),
    "ascii_only": (ascii_only, ["language_encoding_boundary"]),
    "escape_angle": (escape_angle, ["language_section_inverse"]),
    "loads": (loads, ["language_retraction"]),
}

__all__ = ["EXAMPLE_FUNCTIONS", "LEXICON", "SECTIONS", "TAGS", "ascii_only", "collapse_spaces",
           "digits_to_int", "escape_angle", "loads", "unescape_angle"]
