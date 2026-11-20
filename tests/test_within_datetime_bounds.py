# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A datetime bound means the same on every supported Python: its
fraction of a second may have one to six digits, and a spelling that
only some interpreters' `fromisoformat` read is refused on all of them."""
import datetime as dt

import pytest

from mathema_language.text.within import _as_datetime, iso_datetime_within

HALF = dt.datetime(2026, 11, 19, 9, 0, 0, 500000)


@pytest.mark.parametrize("fraction", [".5", ".50", ".500", ".5000", ".50000", ".500000"])
def test_a_fraction_of_one_to_six_digits_is_read(fraction):
    assert _as_datetime("2026-11-19T09:00:00" + fraction) == HALF
    aware = _as_datetime("2026-11-19T09:00:00" + fraction + "+01:00")
    assert aware.replace(tzinfo=None) == HALF and aware.utcoffset() == dt.timedelta(hours=1)


@pytest.mark.parametrize("bound, read", [
    ("2026-11-19", dt.datetime(2026, 11, 19)),
    ("2026-11-19T09", dt.datetime(2026, 11, 19, 9)),
    ("2026-11-19T09:30", dt.datetime(2026, 11, 19, 9, 30)),
    ("2026-11-19 09:30:15", dt.datetime(2026, 11, 19, 9, 30, 15)),
    ("2026-11-19T09:30:15.000001", dt.datetime(2026, 11, 19, 9, 30, 15, 1)),
])
def test_the_spellings_every_python_reads_are_read(bound, read):
    assert _as_datetime(bound) == read


@pytest.mark.parametrize("bound", [
    "2026-11-19T09:00:00.5000000",   # seven fraction digits
    "2026-11-19T09:00:00,5",         # a comma before the fraction
    "2026-11-19T09:00:00Z",          # a Z offset
    "2026-11-19T09:00:00+0100",      # an offset with no colon
    "2026-11-19T09:00:00+01",        # an offset of hours alone
    "20261119T090000",               # the basic format
    "2026-W47-4T09:00:00",           # a week date
    "2026-11-19T09:00:00.",          # a point and no digits
    "2026-11-19T24:00:00",           # hour 24
    "２026-11-19T09:00:00",      # a digit outside ASCII
    "",
])
def test_a_spelling_only_some_pythons_read_is_refused_on_all(bound):
    with pytest.raises(ValueError, match="a datetime bound is"):
        _as_datetime(bound)


def test_an_interval_from_a_half_second_is_built_on_this_python():
    language = iso_datetime_within("2026-11-19T09:00:00.5", "2026-11-19T17:30:00")
    assert language.contains("2026-11-19T09:00:01") and not language.contains("2026-11-19T09:00:00")


def test_a_datetime_itself_is_a_bound():
    assert _as_datetime(HALF) is HALF
    with pytest.raises(ValueError, match="a datetime bound is"):
        _as_datetime(5)
