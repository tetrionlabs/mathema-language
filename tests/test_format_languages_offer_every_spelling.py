# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A format language defined by a parser offers, among its hazards,
every other spelling that parser accepts on the running Python (a basic
or week ISO date, a `Z` offset or a space separator in a datetime), so
a claim that holds only for the canonical spelling is falsified rather
than passing on the spellings the sampler happens to draw. Every hazard
is a member."""
import datetime as dt

import pytest
from mathema.conjecture import check_conjectures, claim

from mathema_language.text import ISO_DATE, ISO_DATETIME


def _accepts(parse, text):
    try:
        parse(text)
    except ValueError:
        return False
    return True


@pytest.mark.parametrize("language", [ISO_DATE, ISO_DATETIME], ids=lambda language: language.name)
def test_every_hazard_is_a_member(language):
    assert all(language.contains(h.value) for h in language.hazards())


@pytest.mark.parametrize("language,parse,spellings", [
    (ISO_DATE, dt.date.fromisoformat, ["20260928", "2026-W39-1", "2026W391"]),
    (ISO_DATETIME, dt.datetime.fromisoformat,
     ["2026-09-28T12:00:00Z", "2026-09-28 12:00:00", "20260928T120000", "2026-09-28"]),
], ids=["iso_date", "iso_datetime"])
def test_each_spelling_the_parser_accepts_is_offered(language, parse, spellings):
    offered = {h.value for h in language.hazards()}
    for text in spellings:
        if _accepts(parse, text):
            assert text in offered, text


def normalise_date(text):
    """A date as YYYY-MM-DD."""
    return dt.date.fromisoformat(text).isoformat()


def test_a_claim_true_only_of_the_canonical_spelling_is_falsified():
    if not _accepts(dt.date.fromisoformat, "20260928"):
        pytest.skip("this Python reads only the extended ISO date")
    (p,) = check_conjectures(normalise_date, [claim("for text in L[iso_date], f(text) == text")])
    assert p.verdict == "falsified", (p.verdict, p.note)
