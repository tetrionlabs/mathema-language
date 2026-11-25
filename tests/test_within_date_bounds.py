# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A date bound means the same on every supported Python: it is written
`YYYY-MM-DD`, and a spelling only some interpreters' `fromisoformat`
read is refused on all of them."""
import datetime as dt

import pytest

from mathema_language.text.within import _as_date, iso_date_within


def test_the_extended_spelling_is_read():
    assert _as_date("2026-09-28") == dt.date(2026, 9, 28)
    assert _as_date("2024-02-29") == dt.date(2024, 2, 29)
    assert _as_date(dt.date(2026, 9, 28)) == dt.date(2026, 9, 28)


@pytest.mark.parametrize("bound", [
    "20260928",            # the basic format
    "2026-W39-1",          # a week date
    "2026W391",            # a basic week date
    "20260928é",      # a basic date and one two-byte character
    "2026W391é",
    "２026-09-28",     # a digit outside ASCII
    "2026-09-28 ",
    "2026-9-28",
    "2026-02-30",          # no such day
    "0000-01-01",          # no such year
    "2026-09-28T00:00:00",
    "",
])
def test_a_spelling_only_some_pythons_read_is_refused_on_all(bound):
    with pytest.raises(ValueError, match="a date bound is"):
        _as_date(bound)


def test_a_datetime_is_no_date_bound():
    with pytest.raises(ValueError, match="a date bound is"):
        _as_date(dt.datetime(2026, 9, 28))


def test_an_interval_refuses_a_basic_bound_on_this_python():
    with pytest.raises(ValueError):
        iso_date_within("20260101", "20261231")
