# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""`len` is this package's refinement, registered under
`mathema.language_refinements`: `L[unicode, len <= 80]` is the members
of a language whose length in code points lies in the bound. Membership
counts code points, samples stay inside, the members at each bound are
the first hazards and plain (`"a" * 80`), the member one past the bound
is the outside draw, the persisted form states the bound in JSON Schema
words, and a `str` annotation carrying a length marker infers the
refined language through the text adaptor."""
import random
from typing import Annotated

import pytest

pytest.importorskip("mathema")

from annotated_types import MaxLen, MinLen  # noqa: E402
from mathema.conjecture import check_conjectures, claim  # noqa: E402
from mathema.domain import parse_binding  # noqa: E402

from mathema_language._surface import refinement_keys, resolve_language  # noqa: E402
from mathema_language.text import adapt  # noqa: E402


def _language(text):
    return resolve_language(parse_binding(f"s in {text}")[1].pieces[0])


def test_len_is_registered_by_the_package():
    assert "len" in refinement_keys()


def test_membership_counts_code_points():
    language = _language("L[ascii, len <= 3]")
    assert language.contains("abc") and language.contains("")
    assert not language.contains("abcd") and not language.contains("é")
    (problem,) = language.explain("abcd")
    assert problem.predicate == "len <= 3"


def test_the_members_at_the_bounds_come_first_and_plain():
    language = _language("L[unicode, len in [2, 80]]")
    assert [h.value for h in language.hazards()][:2] == ["aa", "a" * 80]
    assert language.outside(random.Random(0)) == "a" * 81
    rng = random.Random(1)
    assert all(2 <= len(language.sample(rng)) <= 80 for _ in range(100))


def test_the_persisted_form_states_the_bound():
    schema = _language("L[unicode, len in [2, 80]]").to_json()
    assert (schema["minLength"], schema["maxLength"]) == (2, 80)


def test_a_length_marker_on_str_infers_the_refined_language():
    assert adapt(Annotated[str, MaxLen(8)]).name == "unicode, len <= 8"
    assert adapt(Annotated[str, MinLen(1), MaxLen(8)]).name == "unicode, len in [1, 8]"
    assert adapt(Annotated[str, "a note"]).name == "unicode"

    def pad(s: Annotated[str, MaxLen(8)]) -> str:
        """Padded to eight characters."""
        return s.ljust(8)

    (p,) = check_conjectures(pad, [claim("len(f(s)) == 8")])
    assert p.verdict == "holds", (p.verdict, p.note)
    assert "inferred s in L[unicode, len <= 8]" in p.note
