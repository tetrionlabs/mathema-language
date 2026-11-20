# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The two sides of a pattern's z3 reading, held to `re` on the constructs
a released version read wrongly: a possessive repeat, a repeat of at
most zero, a negated class holding a category, inline flags, and
characters past z3's. The older side admits every string `re.search`
finds the pattern in, the newer side only strings `re.fullmatch`
matches, and an inclusion with a counterexample is never proven."""
import re
import sys

import pytest

z3 = pytest.importorskip("z3")

from mathema_language import smt  # noqa: E402

possessive = pytest.mark.skipif(sys.version_info < (3, 11), reason="possessive repeats need 3.11")


def inside(pattern, side, text):
    solver = z3.Solver()
    solver.add(z3.InRe(z3.StringVal(text), smt.MembershipEncoding(z3)._regex(pattern, side)))
    return solver.check() == z3.sat


def bracketed(pattern, texts):
    """Each text where a side parts from `re`; a refused side parts nowhere."""
    out = []
    for text in texts:
        try:
            if re.search(pattern, text) and not inside(pattern, "older", text):
                out.append(("older", text))
        except smt.Untranslated:
            pass
        try:
            if inside(pattern, "newer", text) and not re.fullmatch(pattern, text):
                out.append(("newer", text))
        except smt.Untranslated:
            pass
    return out


@possessive
@pytest.mark.parametrize("pattern", [r"a*+a", r"a++a", r"a?+a", r"(?:ab){1,2}+ab", r"x(?:a*+a)?"])
def test_a_possessive_repeat_is_refused(pattern):
    with pytest.raises(smt.Untranslated, match="possessive"):
        smt.MembershipEncoding(z3)._regex(pattern, "newer")
    assert bracketed(pattern, ["", "a", "aa", "aaa", "ab", "abab", "ababab", "x", "xa", "xaa"]) == []


@possessive
def test_an_inclusion_into_a_possessive_pattern_is_not_proven():
    pytest.importorskip("jsonschema")

    def schema(pattern):
        return {"type": "object", "required": ["v"],
                "properties": {"v": {"type": "string", "pattern": pattern}}}

    result = smt._schema_inclusion(schema(r"^a+$"), schema(r"^a*+a$"))
    assert result.verdict == "unknown" and "possessive" in result.reason


@pytest.mark.parametrize("pattern", [r"[^\d]", r"[^\w]", r"x[^\d]+", r"[^\w-]"])
def test_a_negated_class_holding_a_category_stays_inside_its_two_sides(pattern):
    assert bracketed(pattern, ["a", "\u0663", "1", "x\u0663", "xa", "-", "\u00e9", " ", ""]) == []


@pytest.mark.parametrize("pattern, texts", [
    (r"(?s)a.b", ["a\nb", "axb"]), (r"(?i)a", ["A", "a"]), (r"(?i:a)b", ["Ab", "ab"]),
    (r"(?m)^a$", ["b\na", "a\nb", "a"]), (r"(?m)a$", ["a\nb"]), (r"(?s:.)", ["\n"]),
    (r"(?is)a.", ["A\n"]), (r"(?i)[^a]", ["A", "b"]), (r"(?i)k", ["\u212a"]),
])
def test_a_flag_stays_inside_its_two_sides(pattern, texts):
    assert bracketed(pattern, texts) == []


@pytest.mark.parametrize("pattern", [r"a*?a", r"a+?", r"[^a]b", r"\d+", r"\w", r"[\d-]", r"a$",
                                     r"a\Z", r"^a", r"(?x) a b", r"(?a)\w", r"a.b", r"[^\n]"])
def test_what_is_read_stays_inside_its_two_sides(pattern):
    texts = ["", "a", "aa", "a\n", "ab", "xb", "1", "٣", "é", "_", "-", "a\nb", "\n",
             "b\na", "xa\n"]
    assert bracketed(pattern, texts) == []
    smt.MembershipEncoding(z3)._regex(pattern, "older")
    smt.MembershipEncoding(z3)._regex(pattern, "newer")


def _model(pattern):
    pydantic = pytest.importorskip("pydantic")

    class M(pydantic.BaseModel):
        s: str = pydantic.Field(pattern=pattern)
    return M


@pytest.mark.parametrize("pattern", [r"a{0}", r"a{0,0}", r"(?:ab){0}", r"xa{0}y", r"[ab]{0}?"])
def test_a_repeat_of_at_most_zero_is_the_empty_string(pattern):
    assert bracketed(pattern, ["", "a", "aa", "aaa", "ab", "xy", "xay", "b"]) == []
    assert not inside(pattern, "newer", "a") or re.fullmatch(pattern, "a")


@pytest.mark.parametrize("older, newer, counterexample", [
    (r"^a{1,3}b", r"^a{0}b(.|\n)*$", "ab"),
    (r"^[^\d]$", r"^b$", "a"),
    ("^٣", r"^[^\d](.|\n)*$", "٣"),
    (r"(?i)^a", r"^a(.|\n)*$", "A"),
    (r"(?s)^a.b", r"^a[^\n]b(.|\n)*$", "a\nb"),
    (r"(?m)^a", r"^a(.|\n)*$", "b\na"),
    (r"(?i)^k", r"^[kK](.|\n)*$", "K"),
    (r"^.", "^[\\x00-\U0002FFFF](.|\\n)*$", "\U00030000"),
    ("^[^a]", "^[\\x00-\U0002FFFF](.|\\n)*$", "\U00030000"),
    ("^[^\U0002FFFF]$", "^[\\x00-\U0002FFFE]$", "\U00030000"),
])
def test_an_inclusion_with_a_counterexample_is_not_proven(older, newer, counterexample):
    assert re.search(older, counterexample) and not re.search(newer, counterexample)
    result = smt._schema_inclusion(_model(older), _model(newer))
    assert result.verdict != "proven", str(result)


def test_the_last_z3_character_stands_for_every_character_past_it():
    last = chr(smt._Z3_MAX_CHAR)
    # a set that holds a character past z3's holds the last one on the older side
    assert inside("[^" + last + "]", "older", last) and inside(".", "older", last)
    # a set that does not hold every character past z3's leaves the last one out on the newer
    assert not inside(last, "newer", last) and not inside("[a-" + last + "]", "newer", last)
    assert inside("[^a]", "newer", last) and inside(last, "older", last)
