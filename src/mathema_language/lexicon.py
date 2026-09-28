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
from typing import Annotated, Any

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
    "record_lift_sign": "for line in L[mathema_language.lexicon.Line], f(line) >= 0",
    # a field with no upper bound
    "record_unbounded_field": "for line in L[mathema_language.lexicon.Line], f(line) <= 100",
    # a text field read through len is a bounded whole number
    "record_length_field": "for line in L[mathema_language.lexicon.Line], f(line) <= 10",
    # one under that bound, a valid record is the witness
    "record_length_field_tight": "for line in L[mathema_language.lexicon.Line], f(line) <= 9",
    # the hazard families over a language
    # paths: bindings that reach into a member through fields and
    # indices, a path past the end or through a missing field reaching
    # the missing value
    "path_every_element": "for o in L[mathema_language.lexicon.Order], o.lines[*].qty in [1, 3], f(o) <= 3",
    "path_every_element_unbound": "for o in L[mathema_language.lexicon.Order], f(o) <= 3",
    "path_nested_present":
        "for o in L[mathema_language.lexicon.Order], o.address.zip in L[digit] \\ {missing}, f(o) == True",
    "path_nested_missing": "for o in L[mathema_language.lexicon.Order], f(o) == True",
    "path_nested_length": "for o in L[mathema_language.lexicon.Order], f(o) <= 5",
    "path_nested_length_tight": "for o in L[mathema_language.lexicon.Order], f(o) <= 4",
    "path_index_present":
        "for o in L[mathema_language.lexicon.Order], o.lines[0].qty in [7, 7] \\ {missing}, f(o) >= 7",
    "path_index_missing": "for o in L[mathema_language.lexicon.Order], o.lines[0].qty in [7, 7], f(o) >= 7",
    # structure: recursive record trees, bounded by depth, nodes and
    # children, and claims about folds over them proven by induction
    "structure_induction_constant": "for t in L[mathema_language.lexicon.Branch, depth <= 20], f(t) >= 1",
    "structure_induction_equation":
        "for t in L[mathema_language.lexicon.Branch, depth <= 20], f(t) == 2 * tree_size(t)",
    "structure_induction_unbounded": "for t in L[mathema_language.lexicon.Branch], f(t) >= 1",
    "structure_induction_base_case": "for t in L[mathema_language.lexicon.Branch, depth <= 20], f(t) >= 2",
    "structure_depth_bound": "for t in L[mathema_language.lexicon.Branch, depth <= 6], f(t) <= 6",
    "structure_depth_bound_tight": "for t in L[mathema_language.lexicon.Branch, depth <= 6], f(t) <= 5",
    "structure_width_bound": "for t in L[mathema_language.lexicon.Branch, depth <= 5, width <= 3], f(t) <= 3",
    "structure_width_one_past": "for t in L[mathema_language.lexicon.Branch, depth <= 5, width <= 4], f(t) <= 3",
    "structure_nodes_bound": "for t in L[mathema_language.lexicon.Branch, nodes <= 50], f(t) <= 50",
    "structure_json_depth": "for s in L[json, depth <= 6], f(f(s)) == f(s)",
    # every language, adaptor and family the package registers
    "language_printable_output": 'for s in L[unicode], f(s) in L[printable]',
    "language_alpha_closure": 'for s in L[alpha] \\ {""}, f(s) in L[alpha]',
    "language_unicode_alpha_closure": 'for s in L[unicode_alpha] \\ {""}, f(s) in L[unicode_alpha]',
    "language_unicode_alnum_length": "for s in L[unicode_alnum], len(f(s)) <= len(s)",
    "language_identifier_closure": 'for s in L[identifier], f(s) in L[identifier]',
    "language_uuid_idempotent": 'for s in L[uuid], f(f(s)) == f(s)',
    "language_uuid_spelling": 'for s in L[uuid], f(s) == s',
    "language_iso_date_idempotent": 'for s in L[iso_date], f(f(s)) == f(s)',
    "language_iso_datetime_idempotent": 'for s in L[iso_datetime], f(f(s)) == f(s)',
    "language_ipv4_closure": 'for s in L[ipv4], f(s) in L[ipv4]',
    "language_ipv6_closure": 'for s in L[ipv6], f(s) in L[ipv6]',
    "language_base64_round_trip": 'for s in L[base64], f(s) == s',
    "language_hex_spelling": 'for s in L[hex], f(s) == s',
    "language_shell_safe_argument": 'for s in L[shell_safe], f(s) == ["rm", s]',
    "language_shell_unsafe_argument": 'for s in L[printable], f(s) == ["rm", s]',
    "language_control_header_injection": 'for s in L[control], "\\n" not in f(s)',
    "language_invisible_blank": 'for s in L[invisible] \\ {""}, f(s) == True',
    "language_combining_stripped": 'for s in L[combining], f(s) == ""',
    "language_surrogate_encoding": 'for s in L[surrogate], is_encoding_safe(s)',
    "language_compatibility_key":
        'let nfkc = mathema_language.text.nfkc, for s in L[compatibility] \\ {""}, f(nfkc(s)) == f(s)',
    "language_astral_utf16": 'for s in L[astral] \\ {""}, f(s) == 2 * len(s)',
    "family_excluded_outside_domain": 'for s in L[uuid], excluded_outside_domain(s)',
    "family_excluded_outside_domain_accepts": 'for s in L[ascii], excluded_outside_domain(s)',
    "vocabulary_tree_depth":
        "let depth = mathema_language.tree.depth, for t in L[mathema_language.lexicon.Branch, depth <= 5], depth(t) == f(t)",
    "adaptor_text_annotation": 'len(f(title)) <= 60',
    "adaptor_pydantic_proven":
        'for form in L[mathema_language._lexicon_models.forms.SignupForm], 0 <= f(form) <= 5',
    "adaptor_pydantic_falsified":
        'for form in L[mathema_language._lexicon_models.forms.SignupForm], f(form) <= 4',
    "adaptor_sqlalchemy_proven":
        'for order in L[mathema_language._lexicon_models.db.Order], f(order) >= 0',
    "adaptor_sqlalchemy_falsified":
        'for order in L[mathema_language._lexicon_models.db.Order], f(order) <= 10000',
    "adaptor_django_proven":
        'for review in L[mathema_language._lexicon_models.reviews.Review], 0 < f(review) <= 1',
    "adaptor_django_falsified":
        'for review in L[mathema_language._lexicon_models.reviews.Review], f(review) >= 0.5',
    "adaptor_jsonschema_proven":
        'for event in L[mathema_language._lexicon_models.webhooks.CHARGE_EVENT], f(event) >= 30',
    "adaptor_jsonschema_falsified":
        'for event in L[mathema_language._lexicon_models.webhooks.CHARGE_EVENT], f(event) in {"billing", "alerts"}',
    "adaptor_typeddict_proven":
        'for hit in L[mathema_language._lexicon_models.search.SearchHit], f(hit) >= 0',
    "adaptor_typeddict_falsified":
        'for hit in L[mathema_language._lexicon_models.search.SearchHit], f(hit) <= 10',
    "family_length_safe": "for s in L[slug], is_length_safe(s)",
    "family_encoding_safe": "for s in L[unicode], is_encoding_safe(s)",
    "family_arbitrary_input": "for s in L[unicode], is_arbitrary_input_safe(s)",
    "closure_ascii_in_ascii_out": "for s in L[ascii], f(s) in L[ascii]",
    "closure_ascii_leaves": "for s in L[ascii], f(s) in L[ascii]",
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
class Address:
    """Where an order ships: a postal code of up to five characters."""
    zip: Annotated[str, MaxLen(5)] | None = None


@dataclass
class OrderLine:
    """One order line: a quantity from one to ten."""
    qty: Annotated[int, Ge(1), Le(10)]


@dataclass
class Order:
    """An order: where it ships and its lines."""
    address: Address
    lines: list[OrderLine] = field(default_factory=list)


def largest_qty(o: Order) -> int:
    """The largest quantity on any line, 0 for no lines."""
    return max((line.qty for line in o.lines), default=0)


def zip_width(o: Order) -> int:
    """The columns the postal code takes, 0 when there is none."""
    return len(o.address.zip) if o.address.zip is not None else 0


def has_zip(o: Order) -> bool:
    """Whether the order has a postal code."""
    return o.address.zip is not None


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


def log_line(s: str) -> str:
    """A message made safe to write to a log file."""
    return "".join(c for c in s if c.isprintable())


def capitalise_word(s: str) -> str:
    """A word with its first letter upper-cased."""
    return s[0].upper() + s[1:]


def attribute_name(s: str) -> str:
    """A form label turned into an attribute name."""
    return s.strip().replace(" ", "_").lower()


def normalise_order_id(s: str) -> str:
    """An order id as the database stores it."""
    import uuid
    return str(uuid.UUID(s))


def parse_order_id(s: str) -> object:
    """The order id in a URL, or a ValueError when it is not one."""
    import uuid
    return uuid.UUID(s)


def normalise_date(s: str) -> str:
    """A date as it is stored."""
    import datetime
    return datetime.date.fromisoformat(s).isoformat()


def normalise_timestamp(s: str) -> str:
    """An event time as it is stored."""
    import datetime
    return datetime.datetime.fromisoformat(s).isoformat()


def anonymise_ip(s: str) -> str:
    """An address with its last part zeroed, written for IPv4."""
    return ".".join(s.split(".")[:3] + ["0"])


def reencode_token(s: str) -> str:
    """A base64 token decoded and encoded again."""
    import base64
    return base64.b64encode(base64.b64decode(s)).decode("ascii")


def normalise_colour(s: str) -> str:
    """Hex bytes as a theme file stores them."""
    return bytes.fromhex(s).hex()


def delete_command(s: str) -> list[str]:
    """The arguments of a delete command built without quoting."""
    import shlex
    return shlex.split(f"rm {s}")


def note_header(s: str) -> str:
    """An HTTP header carrying a free-text note."""
    return "X-Note: " + s


def is_blank(s: str) -> bool:
    """Whether a name has nothing visible in it, by strip."""
    return not s.strip()


def strip_accents(s: str) -> str:
    """The text with its combining marks removed."""
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))


def to_bytes(s: str) -> bytes:
    """The text in UTF-8."""
    return s.encode("utf-8")


def username_key(s: str) -> str:
    """The key an account is stored under, never normalised."""
    return s.strip().lower()


def js_length(s: str) -> int:
    """The length JavaScript reports for the text."""
    return len(s.encode("utf-16-le")) // 2


def shout(s: str) -> str:
    """Upper case, whatever comes in."""
    return s.upper()


def short_title(title: Annotated[str, MaxLen(60)]) -> str:
    """The title, cut to the sixty characters it is declared to fit."""
    return title[:60]


def years_until_adult(form: object) -> int:
    """How long until a signup may see adult content."""
    return max(0, 18 - form.age)  # type: ignore[attr-defined, no-any-return]


def order_total(order: object) -> object:
    """What the customer pays for an order."""
    return order.quantity * order.unit_price  # type: ignore[attr-defined]


def review_weight(review: object) -> float:
    """How much a review counts toward the product's score."""
    return float(review.rating) / 5  # type: ignore[attr-defined]


def processing_fee(event: dict[str, Any]) -> float:
    """The provider's fee on a charge, in cents: 2.9% plus 30."""
    return float(event["amount"] * 0.029 + 30)


def queue_for(event: dict[str, Any]) -> str:
    """The queue a charge event is routed to; the refund queue is missing."""
    return {"charge.succeeded": "billing", "charge.failed": "alerts"}[event["type"]]


def rank(hit: dict[str, Any]) -> float:
    """Where a search hit sorts: relevance first, popularity after."""
    return float(hit["score"] * 10 + hit["clicks"] / 1000)


#: the lexicon's table of contents, every key in exactly one section;
#: installed, mathema reads these as `language/<section>`
SECTIONS: dict[str, tuple[str, ...]] = {
    "domains": ("language_with_special_member",),
    "laws": ("language_homomorphism", "language_section_inverse", "language_retraction",
             "language_idempotent"),
    "boundaries": ("language_encoding_boundary",),
    "length": ("language_length_bound_identity", "language_length_bound_one_past"),
    "membership": ("closure_ascii_in_ascii_out", "closure_ascii_leaves", "in_target_language", "language_closure_rendered",
                   "language_token_absent", "language_token_present"),
    "records": ("record_lift_sign", "record_unbounded_field", "record_length_field",
             "record_length_field_tight"),
    "paths": ("path_every_element", "path_every_element_unbound", "path_nested_present",
              "path_nested_missing", "path_nested_length", "path_nested_length_tight",
              "path_index_present", "path_index_missing"),
    "structure": ("structure_induction_constant", "structure_induction_equation",
                  "structure_induction_unbounded", "structure_induction_base_case",
                  "structure_depth_bound", "structure_depth_bound_tight",
                  "structure_width_bound", "structure_width_one_past",
                  "structure_nodes_bound", "structure_json_depth"),
    "languages": ("language_printable_output", "language_alpha_closure", "language_unicode_alpha_closure",
                  "language_unicode_alnum_length", "language_identifier_closure", "language_uuid_idempotent", "language_uuid_spelling", "language_iso_date_idempotent", "language_iso_datetime_idempotent", "language_ipv4_closure", "language_ipv6_closure", "language_base64_round_trip", "language_hex_spelling", "language_shell_safe_argument", "language_shell_unsafe_argument", "language_control_header_injection", "language_invisible_blank", "language_combining_stripped", "language_surrogate_encoding", "language_compatibility_key", "language_astral_utf16"),
    "adaptors": ("adaptor_text_annotation", "adaptor_pydantic_proven", "adaptor_pydantic_falsified", "adaptor_sqlalchemy_proven", "adaptor_sqlalchemy_falsified", "adaptor_django_proven", "adaptor_django_falsified", "adaptor_jsonschema_proven", "adaptor_jsonschema_falsified", "adaptor_typeddict_proven", "adaptor_typeddict_falsified"),
    "vocabulary": ("vocabulary_tree_depth",),
    "families": ("family_excluded_outside_domain", "family_excluded_outside_domain_accepts",
                 "family_length_safe", "family_encoding_safe", "family_arbitrary_input"),
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
    "record_lift_sign": ("record", "row", "schema", "dataclass"),
    "record_unbounded_field": ("unbounded field", "no upper bound"),
    "record_length_field": ("field length", "maxlen"),
    "record_length_field_tight": ("longest valid value", "column width"),
    "path_every_element": ("every element", "each line", "star path"),
    "path_every_element_unbound": ("nested quantity", "line quantity"),
    "path_nested_present": ("nested field", "required path", "postal code"),
    "path_nested_missing": ("missing nested field", "optional field"),
    "path_nested_length": ("nested max length", "column width"),
    "path_nested_length_tight": ("longest nested value",),
    "path_index_present": ("first element", "index path"),
    "path_index_missing": ("past the end", "empty list", "index out of range"),
    "structure_induction_constant": ("structural induction", "recursive function", "tree size"),
    "structure_induction_equation": ("induction equation", "two recursive functions"),
    "structure_induction_unbounded": ("recursion limit", "recursionerror", "deep tree"),
    "structure_induction_base_case": ("base case", "leaf"),
    "structure_depth_bound": ("tree depth", "nesting bound", "height"),
    "structure_depth_bound_tight": ("deepest member", "depth off by one"),
    "structure_width_bound": ("fan out", "children bound", "width"),
    "structure_width_one_past": ("one child too many", "widest node"),
    "structure_nodes_bound": ("node count", "tree size bound"),
    "structure_json_depth": ("nested json", "canonical json", "sort keys"),
    "language_printable_output": ('printable', 'log line'),
    "language_alpha_closure": ('letters', 'capitalise'),
    "language_unicode_alpha_closure": ('any script', 'capitalise'),
    "language_unicode_alnum_length": ('any script', 'collapse spaces'),
    "language_identifier_closure": ('identifier', 'attribute name'),
    "language_uuid_idempotent": ('uuid', 'normalise id'),
    "language_uuid_spelling": ('uuid spelling', 'hyphenated'),
    "language_iso_date_idempotent": ('iso date', 'date format'),
    "language_iso_datetime_idempotent": ('iso datetime', 'timestamp'),
    "language_ipv4_closure": ('ipv4', 'anonymise ip'),
    "language_ipv6_closure": ('ipv6', 'ipv4 only'),
    "language_base64_round_trip": ('base64', 'token'),
    "language_hex_spelling": ('hex', 'colour'),
    "language_shell_safe_argument": ('shell', 'command line'),
    "language_shell_unsafe_argument": ('shell injection', 'unquoted'),
    "language_control_header_injection": ('control characters', 'header injection'),
    "language_invisible_blank": ('zero width', 'invisible name'),
    "language_combining_stripped": ('combining marks', 'strip accents'),
    "language_surrogate_encoding": ('lone surrogate', 'utf-8'),
    "language_compatibility_key": ('nfkc', 'account takeover'),
    "language_astral_utf16": ('emoji', 'javascript length'),
    "family_excluded_outside_domain": ('reject invalid', 'parser'),
    "family_excluded_outside_domain_accepts": ('accepts invalid', 'no validation'),
    "vocabulary_tree_depth": ('nesting depth', 'tree'),
    "adaptor_text_annotation": ('annotated max length', 'inferred language'),
    "adaptor_pydantic_proven": ('pydantic', 'model'),
    "adaptor_pydantic_falsified": ('pydantic bound', 'form'),
    "adaptor_sqlalchemy_proven": ('sqlalchemy', 'check constraint'),
    "adaptor_sqlalchemy_falsified": ('sqlalchemy', 'table'),
    "adaptor_django_proven": ('django', 'validators'),
    "adaptor_django_falsified": ('django', 'model'),
    "adaptor_jsonschema_proven": ('json schema', 'minimum'),
    "adaptor_jsonschema_falsified": ('json schema', 'webhook'),
    "adaptor_typeddict_proven": ('typeddict', 'annotated'),
    "adaptor_typeddict_falsified": ('typeddict', 'unbounded'),
    "family_length_safe": ("long input", "backtracking", "regex dos"),
    "family_encoding_safe": ("encode", "unicodeencodeerror"),
    "family_arbitrary_input": ("fuzz", "crash", "empty string"),
    "closure_ascii_in_ascii_out": ("output stays", "ascii in ascii out"),
    "closure_ascii_leaves": ("output leaves", "accent"),
}

#: which function each lexicon key is checked against
EXAMPLE_FUNCTIONS: dict[str, tuple[object, list[str]]] = {
    "collapse_spaces": (collapse_spaces, ["language_with_special_member",
                                          "language_idempotent",
                                          "closure_ascii_in_ascii_out",
                                          "language_unicode_alnum_length"]),
    "digits_to_int": (digits_to_int, ["language_homomorphism"]),
    "ascii_only": (ascii_only, ["language_encoding_boundary", "family_encoding_safe"]),
    "headline": (headline, ["language_length_bound_identity",
                            "language_length_bound_one_past"]),
    "slugify": (slugify, ["in_target_language"]),
    "render_count": (render_count, ["language_closure_rendered"]),
    "escape_html": (escape_html, ["language_token_absent", "language_token_present"]),
    "line_total": (line_total, ["record_lift_sign", "record_unbounded_field"]),
    "line_width": (line_width, ["record_length_field", "record_length_field_tight"]),
    "is_slug": (is_slug, ["family_length_safe"]),
    "first": (first, ["family_arbitrary_input"]),
    "accent": (accent, ["closure_ascii_leaves"]),
    "escape_angle": (escape_angle, ["language_section_inverse"]),
    "largest_qty": (largest_qty, ["path_every_element", "path_every_element_unbound",
                                  "path_index_present", "path_index_missing"]),
    "has_zip": (has_zip, ["path_nested_present", "path_nested_missing"]),
    "zip_width": (zip_width, ["path_nested_length", "path_nested_length_tight"]),
    "tree_size": (tree_size, ["structure_induction_constant", "structure_induction_unbounded",
                              "structure_induction_base_case", "structure_nodes_bound"]),
    "tree_twice": (tree_twice, ["structure_induction_equation"]),
    "tree_height": (tree_height, ["structure_depth_bound", "structure_depth_bound_tight",
                                  "vocabulary_tree_depth"]),
    "widest": (widest, ["structure_width_bound", "structure_width_one_past"]),
    "canonical_json": (canonical_json, ["structure_json_depth"]),
    "loads": (loads, ["language_retraction"]),
    "log_line": (log_line, ['language_printable_output']),
    "capitalise_word": (capitalise_word, ['language_alpha_closure', 'language_unicode_alpha_closure']),
    "attribute_name": (attribute_name, ['language_identifier_closure']),
    "normalise_order_id": (normalise_order_id, ['language_uuid_idempotent', 'language_uuid_spelling']),
    "normalise_date": (normalise_date, ['language_iso_date_idempotent']),
    "normalise_timestamp": (normalise_timestamp, ['language_iso_datetime_idempotent']),
    "anonymise_ip": (anonymise_ip, ['language_ipv4_closure', 'language_ipv6_closure']),
    "reencode_token": (reencode_token, ['language_base64_round_trip']),
    "normalise_colour": (normalise_colour, ['language_hex_spelling']),
    "delete_command": (delete_command, ['language_shell_safe_argument', 'language_shell_unsafe_argument']),
    "note_header": (note_header, ['language_control_header_injection']),
    "is_blank": (is_blank, ['language_invisible_blank']),
    "strip_accents": (strip_accents, ['language_combining_stripped']),
    "to_bytes": (to_bytes, ['language_surrogate_encoding']),
    "username_key": (username_key, ['language_compatibility_key']),
    "js_length": (js_length, ['language_astral_utf16']),
    "parse_order_id": (parse_order_id, ['family_excluded_outside_domain']),
    "shout": (shout, ['family_excluded_outside_domain_accepts']),
    "short_title": (short_title, ['adaptor_text_annotation']),
    "years_until_adult": (years_until_adult, ['adaptor_pydantic_proven', 'adaptor_pydantic_falsified']),
    "order_total": (order_total, ['adaptor_sqlalchemy_proven', 'adaptor_sqlalchemy_falsified']),
    "review_weight": (review_weight, ['adaptor_django_proven', 'adaptor_django_falsified']),
    "processing_fee": (processing_fee, ['adaptor_jsonschema_proven']),
    "queue_for": (queue_for, ['adaptor_jsonschema_falsified']),
    "rank": (rank, ['adaptor_typeddict_proven', 'adaptor_typeddict_falsified']),
}

__all__ = ["EXAMPLE_FUNCTIONS", "LEXICON", "SECTIONS", "TAGS", "Address", "Branch", "Line",
           "Order", "OrderLine", "accent", "ascii_only", "canonical_json", "collapse_spaces", "digits_to_int", "escape_angle", "escape_html", "first", "has_zip", "largest_qty",
           "headline", "is_slug", "line_total", "line_width", "loads", "render_count",
           "slugify", "tree_height", "tree_size", "tree_twice", "unescape_angle", "widest", "zip_width"]
