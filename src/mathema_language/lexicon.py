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

import html
import json
import re
from dataclasses import dataclass, field
from typing import Annotated

try:
    from annotated_types import Ge, Le, MaxLen
except ImportError:
    # the adaptors read a marker by its attribute, so a class with the
    # same attribute is the same marker
    @dataclass(frozen=True)
    class Ge:  # type: ignore[no-redef]
        ge: float

    @dataclass(frozen=True)
    class Le:  # type: ignore[no-redef]
        le: float

    @dataclass(frozen=True)
    class MaxLen:  # type: ignore[no-redef]
        max_length: int

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
    # a length bound: inside it the cut changes nothing
    "language_length_bound_identity": "for s in L[unicode, len <= 80], f(s) == s",
    # one past the bound, the member at the bound loses a character
    "language_length_bound_one_past": "for s in L[unicode, len <= 81], f(s) == s",
    # closure into a language other than the input's own
    "in_target_language": "for s in L[unicode], f(s) in L[slug]",
    # a renderer's output held to a language
    "language_closure_rendered": "for n in N, f(n) in L[digit]",
    # containment: a token that never survives
    "language_token_absent": 'for s in L[unicode], "<" not in f(s)',
    # containment that fails: the escape character itself
    "language_token_present": 'for s in L[unicode], "&" not in f(s)',
    # a row language: the lift reads the fields' bounds and proves
    "row_lift_sign": "for line in L[mathema_language.lexicon.Line], f(line) >= 0",
    # a field with no upper bound
    "row_unbounded_field": "for line in L[mathema_language.lexicon.Line], f(line) <= 100",
    # a text field read through len is a bounded whole number
    "row_length_field": "for line in L[mathema_language.lexicon.Line], f(line) <= 10",
    # one under that bound, a valid record is the witness
    "row_length_field_tight": "for line in L[mathema_language.lexicon.Line], f(line) <= 9",
    # the hazard families over a language
    # structure: recursive record trees, bounded by depth, nodes and
    # children, and claims about folds over them proven by induction
    "structure_induction_constant": "for t in L[mathema_language.lexicon.Branch, depth <= 20], f(t) >= 1",
    "structure_induction_equation":
        "for t in L[mathema_language.lexicon.Branch, depth <= 20], f(t) == 2 * tree_size(t)",
    "structure_induction_unbounded": "for t in L[mathema_language.lexicon.Branch], f(t) >= 1",
    "structure_induction_base_case": "for t in L[mathema_language.lexicon.Branch, depth <= 20], f(t) >= 2",
    "structure_depth_bound": "for t in L[mathema_language.lexicon.Branch, depth <= 6], f(t) <= 6",
    "structure_depth_bound_tight": "for t in L[mathema_language.lexicon.Branch, depth <= 6], f(t) <= 5",
    "structure_children_bound": "for t in L[mathema_language.lexicon.Branch, depth <= 5, children <= 3], f(t) <= 3",
    "structure_children_one_past": "for t in L[mathema_language.lexicon.Branch, depth <= 5, children <= 4], f(t) <= 3",
    "structure_nodes_bound": "for t in L[mathema_language.lexicon.Branch, nodes <= 50], f(t) <= 50",
    "structure_json_depth": "for s in L[json, depth <= 6], f(f(s)) == f(s)",
    "family_length_safe": "for s in L[slug], is_length_safe(s)",
    "family_encoding_safe": "for s in L[unicode], is_encoding_safe(s)",
    "family_arbitrary_input": "for s in L[unicode], is_arbitrary_input_safe(s)",
    "family_output_in_language": "for s in L[ascii], output_in_language(f(s))",
    "family_output_leaves_language": "for s in L[ascii], output_in_language(f(s))",
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


@dataclass
class Line:
    """An order line: a short sku, a quantity from one to ten, a price
    of at least zero."""
    sku: Annotated[str, MaxLen(8)]
    qty: Annotated[int, Ge(1), Le(10)]
    price: Annotated[float, Ge(0.0)]


def headline(s: str) -> str:
    """At most eighty characters of s."""
    return s[:80]


def slugify(s: str) -> str:
    """The lower-case ASCII words of s, joined by hyphens."""
    return "-".join(re.findall(r"[a-z0-9]+", s.lower()))


def render_count(n: int) -> str:
    """The decimal spelling of a count."""
    return str(n)


def escape_html(s: str) -> str:
    """The s with its markup characters as entities."""
    return html.escape(s)


def line_total(line: Line) -> float:
    """Quantity times price."""
    return line.qty * line.price


def line_width(line: Line) -> int:
    """The columns the sku takes, with a space either side."""
    return len(line.sku) + 2


def is_slug(s: str) -> bool:
    """Whether s is a slug."""
    return re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", s) is not None


def first(s: str) -> str:
    """The first character."""
    return s[0]


def accent(s: str) -> str:
    """An accent appended."""
    return s + "\u00e9"


@dataclass
class Branch:
    """A tree node: a label and its children."""
    label: int
    children: list[Branch] = field(default_factory=list)


def tree_size(t: Branch) -> int:
    """How many nodes, counted recursively."""
    return 1 + sum(tree_size(c) for c in t.children)


def tree_twice(t: Branch) -> int:
    """Twice the node count, counted recursively."""
    return 2 + sum(tree_twice(c) for c in t.children)


def tree_height(t: Branch) -> int:
    """How many levels of nodes, counted recursively."""
    return 1 + max((tree_height(c) for c in t.children), default=0)


def widest(t: Branch) -> int:
    """The most children any node has."""
    return max([len(t.children), *(widest(c) for c in t.children)])


def canonical_json(s: str) -> str:
    """The JSON document with its keys sorted."""
    return json.dumps(json.loads(s), sort_keys=True)


#: the lexicon's table of contents, every key in exactly one section;
#: installed, mathema reads these as `language/<section>`
SECTIONS: dict[str, tuple[str, ...]] = {
    "domains": ("language_with_special_member",),
    "laws": ("language_homomorphism", "language_section_inverse", "language_retraction",
             "language_idempotent"),
    "boundaries": ("language_encoding_boundary",),
    "length": ("language_length_bound_identity", "language_length_bound_one_past"),
    "membership": ("in_target_language", "language_closure_rendered",
                   "language_token_absent", "language_token_present"),
    "rows": ("row_lift_sign", "row_unbounded_field", "row_length_field",
             "row_length_field_tight"),
    "structure": ("structure_induction_constant", "structure_induction_equation",
                  "structure_induction_unbounded", "structure_induction_base_case",
                  "structure_depth_bound", "structure_depth_bound_tight",
                  "structure_children_bound", "structure_children_one_past",
                  "structure_nodes_bound", "structure_json_depth"),
    "families": ("family_length_safe", "family_encoding_safe", "family_arbitrary_input",
                 "family_output_in_language", "family_output_leaves_language"),
}

#: everyday words each row is found by through `mathema.lexicon.find`
TAGS: dict[str, tuple[str, ...]] = {
    "language_with_special_member": ("sentinel", "placeholder value", "union with a set"),
    "language_homomorphism": ("homomorphism", "append a digit", "parse digits"),
    "language_encoding_boundary": ("encoding error", "codec", "latin-1"),
    "language_section_inverse": ("round trip", "inverse", "unescape"),
    "language_retraction": ("retraction", "parse render parse", "json round trip"),
    "language_idempotent": ("idempotent", "normaliser", "apply twice"),
    "language_length_bound_identity": ("truncate", "length bound", "max length"),
    "language_length_bound_one_past": ("one past the bound", "truncation bug"),
    "in_target_language": ("slugify", "closure", "output language"),
    "language_closure_rendered": ("renderer output", "digits only"),
    "language_token_absent": ("never emits", "token absent", "escape angle brackets"),
    "language_token_present": ("escape character", "ampersand"),
    "row_lift_sign": ("row", "record", "schema", "dataclass"),
    "row_unbounded_field": ("unbounded field", "no upper bound"),
    "row_length_field": ("field length", "maxlen"),
    "row_length_field_tight": ("longest valid value", "column width"),
    "structure_induction_constant": ("structural induction", "recursive function", "tree size"),
    "structure_induction_equation": ("induction equation", "two recursive functions"),
    "structure_induction_unbounded": ("recursion limit", "recursionerror", "deep tree"),
    "structure_induction_base_case": ("base case", "leaf"),
    "structure_depth_bound": ("tree depth", "nesting bound", "height"),
    "structure_depth_bound_tight": ("deepest member", "depth off by one"),
    "structure_children_bound": ("fan out", "children bound", "width"),
    "structure_children_one_past": ("one child too many", "widest node"),
    "structure_nodes_bound": ("node count", "tree size bound"),
    "structure_json_depth": ("nested json", "canonical json", "sort keys"),
    "family_length_safe": ("long input", "backtracking", "regex dos"),
    "family_encoding_safe": ("encode", "unicodeencodeerror"),
    "family_arbitrary_input": ("fuzz", "crash", "empty string"),
    "family_output_in_language": ("output stays", "ascii in ascii out"),
    "family_output_leaves_language": ("output leaves", "accent"),
}

#: which function each lexicon key is checked against
EXAMPLE_FUNCTIONS: dict[str, tuple[object, list[str]]] = {
    "collapse_spaces": (collapse_spaces, ["language_with_special_member",
                                          "language_idempotent",
                                          "family_output_in_language"]),
    "digits_to_int": (digits_to_int, ["language_homomorphism"]),
    "ascii_only": (ascii_only, ["language_encoding_boundary", "family_encoding_safe"]),
    "headline": (headline, ["language_length_bound_identity",
                            "language_length_bound_one_past"]),
    "slugify": (slugify, ["in_target_language"]),
    "render_count": (render_count, ["language_closure_rendered"]),
    "escape_html": (escape_html, ["language_token_absent", "language_token_present"]),
    "line_total": (line_total, ["row_lift_sign", "row_unbounded_field"]),
    "line_width": (line_width, ["row_length_field", "row_length_field_tight"]),
    "is_slug": (is_slug, ["family_length_safe"]),
    "first": (first, ["family_arbitrary_input"]),
    "accent": (accent, ["family_output_leaves_language"]),
    "escape_angle": (escape_angle, ["language_section_inverse"]),
    "tree_size": (tree_size, ["structure_induction_constant", "structure_induction_unbounded",
                              "structure_induction_base_case", "structure_nodes_bound"]),
    "tree_twice": (tree_twice, ["structure_induction_equation"]),
    "tree_height": (tree_height, ["structure_depth_bound", "structure_depth_bound_tight"]),
    "widest": (widest, ["structure_children_bound", "structure_children_one_past"]),
    "canonical_json": (canonical_json, ["structure_json_depth"]),
    "loads": (loads, ["language_retraction"]),
}

__all__ = ["EXAMPLE_FUNCTIONS", "LEXICON", "SECTIONS", "TAGS", "Branch", "Line", "accent",
           "ascii_only", "canonical_json", "collapse_spaces", "digits_to_int", "escape_angle", "escape_html", "first",
           "headline", "is_slug", "line_total", "line_width", "loads", "render_count",
           "slugify", "tree_height", "tree_size", "tree_twice", "unescape_angle", "widest"]
