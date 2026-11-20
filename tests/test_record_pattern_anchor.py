# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A pattern on a field of a JSON Schema record is read on both sides of
an inclusion as the `jsonschema` validator reads it, by `re.search`, so
a pattern ending in `$` is the same language on the two sides and an
inclusion between two such patterns is decided."""
import itertools

import pytest

pytest.importorskip("z3")
pytest.importorskip("jsonschema")

from mathema_language import smt  # noqa: E402
from mathema_language.schema.adaptors import adapt_row  # noqa: E402

DEEP = r"^/wt/task-7(/[a-z0-9_.-]+)*$"
SHALLOW = r"^/wt(/[a-z0-9_.-]+)*$"


def record(pattern):
    return {"type": "object", "required": ["root"], "additionalProperties": False,
            "properties": {"root": {"type": "string", "pattern": pattern}}}


def admits(pattern, text):
    return adapt_row(record(pattern)).contains({"root": text})


@pytest.mark.parametrize("older, newer", [
    (DEEP, SHALLOW), (r"^a$", r"^a$"), (r"^ab$", r"^a[a-z]*$"), (r"^a(?:bc)*$", r"^a(?:bc)*$"),
    (r"^a\Z", r"^a$"), (r"a$", r"a"), (r"^a$", r"a$"),
])
def test_an_inclusion_between_dollar_anchored_patterns_is_proven(older, newer):
    result = smt._schema_inclusion(record(older), record(newer))
    assert result.verdict == "proven", result


def test_the_proven_inclusion_holds_on_every_short_path():
    parts = ("/wt", "/task-7", "/a", "/a.b", "\n", "x", "/")
    texts = {"".join(t) for n in range(5) for t in itertools.product(parts, repeat=n)}
    inside = [t for t in texts if admits(DEEP, t)]
    assert len(inside) >= 20 and "/wt/task-7\n" in inside
    assert [t for t in inside if not admits(SHALLOW, t)] == []


@pytest.mark.parametrize("older, newer", [
    (SHALLOW, DEEP), (r"^a$", r"^a\Z"), (r"a", r"^a$"), (r"^a[a-z]*$", r"^ab$"),
])
def test_the_other_direction_is_falsified_by_a_record_both_validations_confirm(older, newer):
    result = smt._schema_inclusion(record(older), record(newer))
    assert result.verdict == "falsified", result
    text = result.witness["root"]
    assert admits(older, text) and not admits(newer, text)


def test_a_trailing_newline_separates_dollar_from_the_end_of_text():
    result = smt._schema_inclusion(record(r"^a$"), record(r"^a\Z"))
    assert result.witness == {"root": "a\n"}


def test_a_pattern_read_alone_still_has_its_two_sides():
    z3 = pytest.importorskip("z3")
    encoding = smt.MembershipEncoding(z3)
    x = z3.String("x")
    solver = z3.Solver()
    solver.add(z3.InRe(x, encoding._regex(r"^a$", "older")),
               z3.Not(z3.InRe(x, encoding._regex(r"^a$", "newer"))))
    assert solver.check() == z3.sat
