# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The claims written on the `within` membership functions, checked by
mathema and pinned: the standard library's reading, the pattern and the
term agree on members of the base language and on arbitrary text, a
region inside another lets nothing escape, and the converse has a named
witness."""
import re

import pytest

mathema = pytest.importorskip("mathema")

import mathema_language.text.within as within  # noqa: E402

FUNCTIONS = [within._reads, within._escapes, within._matches, within._in_term]


def _declared(fn) -> list[str]:
    """The names of the claims in a function's `Claims:` section."""
    section = fn.__doc__.split("Claims:")[1].split("Raises:")[0]
    return re.findall(r"^\s+(\w+): ", section, flags=re.MULTILINE)


@pytest.mark.parametrize("fn", FUNCTIONS, ids=lambda fn: fn.__name__)
def test_every_declared_claim_holds(fn):
    names = _declared(fn)
    assert len(names) >= 3
    verdicts = {p.name: (p.verdict, p.note) for p in mathema.check(fn).probes if p.name in names}
    assert sorted(verdicts) == sorted(names)
    assert {name: v for name, (v, _) in verdicts.items() if v not in ("holds", "proven")} == {}, verdicts
