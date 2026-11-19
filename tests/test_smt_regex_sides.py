# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The two sides of a pattern's z3 reading, held to `re` on constructs
where the reading could part from it: the older side admits every
string `re.search` finds the pattern in, the newer side only strings
`re.fullmatch` matches, and a construct read neither way is refused by
name."""
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
def test_the_newer_side_refuses_a_possessive_repeat(pattern):
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
def test_a_negated_class_holding_a_category_is_refused(pattern):
    for side in ("older", "newer"):
        with pytest.raises(smt.Untranslated, match="negated"):
            smt.MembershipEncoding(z3)._regex(pattern, side)


@pytest.mark.parametrize("pattern, texts", [
    (r"(?s)a.b", ["a\nb", "axb"]), (r"(?i)a", ["A", "a"]), (r"(?i:a)b", ["Ab", "ab"]),
    (r"(?m)^a$", ["b\na", "a\nb", "a"]), (r"(?m)a$", ["a\nb"]), (r"(?s:.)", ["\n"]),
    (r"(?is)a.", ["A\n"]),
])
def test_the_older_side_refuses_a_flag_it_does_not_read(pattern, texts):
    with pytest.raises(smt.Untranslated, match="flag"):
        smt.MembershipEncoding(z3)._regex(pattern, "older")
    assert bracketed(pattern, texts) == []


@pytest.mark.parametrize("pattern", [r"a*?a", r"a+?", r"[^a]b", r"\d+", r"\w", r"[\d-]", r"a$",
                                     r"a\Z", r"^a", r"(?x) a b", r"(?a)\w", r"a.b", r"[^\n]"])
def test_what_is_read_stays_inside_its_two_sides(pattern):
    texts = ["", "a", "aa", "a\n", "ab", "xb", "1", "٣", "é", "_", "-", "a\nb", "\n",
             "b\na", "xa\n"]
    assert bracketed(pattern, texts) == []
    smt.MembershipEncoding(z3)._regex(pattern, "older")
    smt.MembershipEncoding(z3)._regex(pattern, "newer")
