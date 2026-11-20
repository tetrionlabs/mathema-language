# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Each named format language states its regular-language definition.

The definition is checked against the language's own `contains`: on
every string up to a length over one character from each set the term
tells apart (its atoms) together with a newline, a space and a letter
outside ASCII; on the language's draws and hazards; on every draw with
one character deleted, replaced or inserted; and on strings drawn from
the term itself. An exact term must agree with `contains` everywhere; a
bounds pair must hold every member in `at_least` and only members in
`at_most`.
"""
import itertools
import random
import sys

import pytest

from mathema_language.refinements import length, length_bound
from mathema_language.text import LANGUAGES
from mathema_language.text import _regular as rx
from mathema_language.text.path_language import PATH

#: the exact languages, with the length every string is tried up to
EXACT = {"slug": 5, "hex": 5, "base64": 4, "ipv4": 4, "ipv6": 4, "shell_safe": 4, "path": 4}
BOUNDED = {"identifier": 4, "uuid": 4, "iso_date": 4, "iso_datetime": 4}
NOT_REGULAR = ("json", "yaml", "toml")
EXTRA = ("\n", " ", "é")


def _language(name):
    if name == "path":
        return PATH
    if name in LANGUAGES:
        return LANGUAGES[name]
    module = pytest.importorskip(f"mathema_language.text.{name}_language")
    return getattr(module, f"{name.upper()}_TEXT")


def _nodes(doc):
    return [doc["language"]] if doc["exact"] else [doc["at_least"], doc["at_most"]]


def atoms(doc):
    """One character from each set of characters the term's nodes do not
    tell apart, a printable ASCII one where the set has one."""
    sets = set()
    for node in _nodes(doc):
        rx._re_sets(rx.from_node(node), sets)
    cuts = sorted({0, 0x110000} | {edge for s in sets for lo, hi in s for edge in (lo, hi + 1)})
    chosen = {}
    for start, end in zip(cuts, cuts[1:], strict=False):
        signature = frozenset(s for s in sets if rx._cs_has(s, start))
        shown = next((c for c in range(max(start, 0x21), min(end, 0x7F))), None)
        if signature not in chosen or (shown is not None and not 0x21 <= chosen[signature] < 0x7F):
            chosen[signature] = start if shown is None else shown
    return [chr(c) for c in chosen.values()]


def strings(chars, longest):
    yield ""
    for n in range(1, longest + 1):
        for letters in itertools.product(chars, repeat=n):
            yield "".join(letters)


def tried(doc, longest):
    """The characters tried for a term and the length they are tried to: the full length for a
    term of at most sixteen characters, one less for each doubling past that."""
    chars = list(dict.fromkeys([*atoms(doc), *EXTRA]))
    while longest > 2 and len(chars) ** longest > 400_000:
        longest -= 1
    return chars, longest


def agrees(language, doc, text):
    """Why the term and `contains` disagree on `text`, or None."""
    inside = language.contains(text)
    if doc["exact"]:
        return None if rx.member(doc, text) == inside else f"the term and contains differ on {text!r}"
    if inside and not rx.member(doc, text, "at_least"):
        return f"{text!r} is a member outside at_least"
    if not inside and rx.member(doc, text, "at_most"):
        return f"{text!r} is in at_most and is no member"
    return None


def drawn(node, rng):
    """A string of a node's language, for a node of literals, character sets, concatenations,
    unions and repeats."""
    op = node["op"]
    if op == "epsilon":
        return ""
    if op == "literal":
        return "".join(map(chr, node["codes"]))
    if op == "chars":
        lo, hi = rng.choice(node["ranges"])
        return chr(rng.choice([lo, hi, rng.randint(lo, hi)]))
    if op == "concat":
        return "".join(drawn(a, rng) for a in node["args"])
    if op == "union":
        return drawn(rng.choice(node["args"]), rng)
    assert op == "repeat", op
    most = node["min"] + 3 if node["max"] is None else node["max"]
    return "".join(drawn(node["arg"], rng) for _ in range(rng.randint(node["min"], most)))


@pytest.fixture(scope="module", params=[*EXACT, *BOUNDED])
def stated(request):
    language = _language(request.param)
    doc = language.to_json().get("definition")
    assert isinstance(doc, dict), f"L[{request.param}] states no definition"
    return request.param, language, doc


def test_the_definition_is_a_term_of_the_kind_stated(stated):
    name, _, doc = stated
    assert doc["kind"] == "regular_language" and doc["version"] == rx.TERM_VERSION
    assert doc["exact"] is (name in EXACT)
    assert len(rx.term_hash(doc)) == 64
    if not doc["exact"]:
        assert doc["source"]["not_exact"]


def test_the_term_agrees_with_contains_on_every_short_string(stated):
    name, language, doc = stated
    chars, longest = tried(doc, {**EXACT, **BOUNDED}[name])
    wrong = [why for text in strings(chars, longest) if (why := agrees(language, doc, text))]
    assert wrong[:5] == []


def test_draws_and_hazards_are_inside(stated):
    _, language, doc = stated
    rng = random.Random(20261120)
    members = [h.value for h in language.hazards()] + [language.sample(rng) for _ in range(300)]
    bound = "language" if doc["exact"] else "at_least"
    assert [m for m in members if isinstance(m, str) and not rx.member(doc, m, bound)] == []


def test_the_term_agrees_with_contains_one_edit_from_a_member(stated):
    _, language, doc = stated
    rng = random.Random(20261121)
    chars = list(dict.fromkeys([*atoms(doc), *EXTRA]))
    members = sorted({m for m in ([h.value for h in language.hazards()]
                                  + [language.sample(rng) for _ in range(40)])
                      if isinstance(m, str) and len(m) <= 48})
    wrong = []
    for member in members:
        edits = {member[:i] + member[i + 1:] for i in range(len(member))}
        for i in range(len(member) + 1):
            for c in chars:
                edits.add(member[:i] + c + member[i:])
                if i < len(member):
                    edits.add(member[:i] + c + member[i + 1:])
        wrong.extend(why for text in sorted(edits) if (why := agrees(language, doc, text)))
    assert wrong[:5] == []


def test_strings_drawn_from_the_term_are_members(stated):
    name, language, doc = stated
    if name == "identifier":
        pytest.skip("its at_most is over each character class, checked character by character")
    rng = random.Random(20261122)
    node = doc["language"] if doc["exact"] else doc["at_most"]
    texts = {drawn(node, rng) for _ in range(400)}
    assert sorted(t for t in texts if not language.contains(t))[:5] == []


def test_shell_safe_is_every_nonempty_string_over_the_characters_quote_leaves():
    language = LANGUAGES["shell_safe"]
    kept = {c for c in range(0x110000) if language.contains(chr(c))}
    sets = rx._re_sets(rx.from_node(language.to_json()["definition"]["language"]), set())
    assert {c for s in sets for lo, hi in s for c in range(lo, hi + 1)} == kept
    assert not language.contains("") and language.contains("a.b") and not language.contains("a b")


def test_an_identifier_is_a_first_character_then_later_ones_on_this_python():
    language, doc = LANGUAGES["identifier"], LANGUAGES["identifier"].to_json()["definition"]
    first = {c for c in range(0x110000) if chr(c).isidentifier()}
    later = {c for c in range(0x110000) if ("a" + chr(c)).isidentifier()}
    for bound, holds in (("at_least", lambda own, stated: own <= stated),
                         ("at_most", lambda own, stated: stated <= own)):
        start, rest = doc[bound]["args"][0], doc[bound]["args"][1]["arg"]
        assert holds(first, {c for lo, hi in start["ranges"] for c in range(lo, hi + 1)}), bound
        assert holds(later, {c for lo, hi in rest["ranges"] for c in range(lo, hi + 1)}), bound
    for text in ("a", "_", "a1", "été", "Ⅰ"):
        assert language.contains(text) and rx.member(doc, text, "at_least")
    for text in ("", "1a", "a b", "a\n", "a-b"):
        assert not language.contains(text) and not rx.member(doc, text, "at_least")


@pytest.mark.parametrize("name", NOT_REGULAR)
def test_a_language_that_is_not_regular_says_so_in_the_definition_s_place(name):
    form = _language(name).to_json()
    assert "definition" not in form
    assert "not regular" in form["no_definition"]


def test_a_length_bound_on_a_format_language_cuts_its_definition():
    bounded = length(LANGUAGES["slug"], length_bound(0, 4)).to_json()["definition"]
    assert bounded["exact"]
    for text in ("a", "a-b", "ab-c", "abcde", "a-b-c", "", "-a"):
        assert rx.member(bounded, text) == (LANGUAGES["slug"].contains(text) and len(text) <= 4)


def test_a_length_bound_on_a_language_that_is_not_regular_states_neither():
    form = length(LANGUAGES["json"], length_bound(0, 4)).to_json()
    assert "definition" not in form and "no_definition" not in form
    assert "no_definition" in length(LANGUAGES["json"], length_bound(2, None)).to_json()


@pytest.mark.parametrize("name", sorted(LANGUAGES))
def test_every_registered_text_language_states_a_definition_or_why_not(name):
    form = LANGUAGES[name].to_json()
    assert ("definition" in form) != ("no_definition" in form)


def test_ipv4_agrees_on_every_four_part_address_of_boundary_octets():
    language, doc = LANGUAGES["ipv4"], LANGUAGES["ipv4"].to_json()["definition"]
    octets = ("", "0", "1", "9", "00", "01", "10", "99", "100", "199", "200", "249", "250",
              "255", "256", "260", "300", "999", "1000")
    texts = [".".join(parts) for parts in itertools.product(octets, repeat=4)]
    assert sum(map(language.contains, texts)) == 11 ** 4
    assert [t for t in texts if rx.member(doc, t) != language.contains(t)][:5] == []


def test_which_pythons_read_a_basic_date_followed_by_one_two_byte_character():
    language, doc = LANGUAGES["iso_date"], LANGUAGES["iso_date"].to_json()["definition"]
    odd = ("20260928\u00e9", "2026W391\u00e9", "20260928\u0080")
    if sys.version_info[:2] > (3, 14):
        pytest.skip("not recorded for this Python yet")
    reads = sys.version_info[:2] >= (3, 11)
    assert [language.contains(text) for text in odd] == [reads] * 3
    for text in odd:
        assert rx.member(doc, text, "at_least") and not rx.member(doc, text, "at_most")
    for text in ("2026-09-28\u00e9", "20260928\u0800", "20260928x", "2026092\u00e9"):
        assert not language.contains(text)


def test_the_identifier_table_is_this_python_s_own_reading():
    from mathema_language.text._named_terms import identifier_characters
    here = f"{sys.version_info[0]}.{sys.version_info[1]}"
    sets = identifier_characters()
    if here not in sets["versions"]:
        pytest.skip(f"the table has no entry for Python {here}")
    own = {"start": {c for c in range(0x110000) if chr(c).isidentifier()},
           "continue": {c for c in range(0x110000) if ("a" + chr(c)).isidentifier()}}
    for name, expected in own.items():
        stated = {c for lo, hi in sets[name]["by_version"][here] for c in range(lo, hi + 1)}
        assert stated == expected, name
    assert sets["versions"] == rx.versions_data()["versions"]
