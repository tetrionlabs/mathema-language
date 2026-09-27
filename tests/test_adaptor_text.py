# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The text adaptor: `str` is every string, `Annotated[str, ...]` every
string refined by the length markers it carries, and it answers not
mine for every other annotation."""
from typing import Annotated

from annotated_types import MaxLen

from mathema_language.conformance import FOREIGN, not_mine_problems
from mathema_language.text import UNICODE, adapt


def test_str_and_annotated_str_are_unicode():
    assert adapt(str) is UNICODE
    assert adapt(Annotated[str, "a note"]) is UNICODE
    assert adapt(Annotated[str, MaxLen(80)]).name == "unicode, len <= 80"


def test_not_mine():
    assert adapt(Annotated[int, MaxLen(3)]) is None
    assert not_mine_problems(adapt, foreign=tuple(x for x in FOREIGN if x is not str)) == []
