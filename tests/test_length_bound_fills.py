# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A length bound visits, beside the plain member at the bound, each
character whose length changes under case mapping or Unicode
normalisation repeated up to the bound, so a claim that an output fits
a column the input fits is falsified by the input that grows the most,
not only by a single such character far from the bound."""
import pytest

pytest.importorskip("mathema")

from mathema.conjecture import check_conjectures, claim  # noqa: E402
from mathema.domain import parse_binding  # noqa: E402
from mathema.languages import resolve_language  # noqa: E402

from tests import _length_changing as fns  # noqa: E402


def _language(text):
    return resolve_language(parse_binding(f"s in {text}")[1].pieces[0])


def test_length_changing_characters_are_filled_to_the_bound():
    values = [h.value for h in _language("L[unicode, len <= 32]").hazards()]
    assert "ß" * 32 in values and "ﬁ" * 32 in values
    assert all(len(v) <= 32 for v in values if isinstance(v, str))


def test_an_alphabet_with_no_such_character_gains_nothing():
    plain = [h.value for h in _language("L[ascii, len <= 8]").hazards()]
    assert not any(isinstance(v, str) and len(v) == 8 and len(set(v)) == 1 and v != "a" * 8
                   for v in plain), plain


def test_an_output_that_outgrows_the_column_is_falsified():
    (p,) = check_conjectures(fns.display_name, [claim(
        "for username in L[unicode, len <= 32], len(f(username)) <= 32")])
    assert p.verdict == "falsified", (p.verdict, p.note)
