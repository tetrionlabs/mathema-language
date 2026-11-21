# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The claims written on the shape and explain functions, checked by
mathema and pinned: a shape's own reading, its pattern and its term
agree on text of several languages, the widest shapes admit every text
of their base, canonical text is settled, and a reading does not depend
on how a pattern spells one language."""
import re

import pytest

mathema = pytest.importorskip("mathema")

import mathema_language.text.explain as explain  # noqa: E402
import mathema_language.text.shape as shape  # noqa: E402

FUNCTIONS = [shape._reads, shape._pattern_reads, shape._term_reads, shape._canonical, explain._reading]


def _declared(fn) -> list[str]:
    """The names of the claims in a function's `Claims:` section."""
    section = fn.__doc__.split("Claims:")[1].split("Raises:")[0]
    return re.findall(r"^\s+(\w+): ", section, flags=re.MULTILINE)


@pytest.mark.running_unicode
@pytest.mark.parametrize("fn", FUNCTIONS, ids=lambda fn: fn.__name__)
def test_every_declared_claim_holds(fn):
    names = _declared(fn)
    assert len(names) >= 3
    verdicts = {p.name: (p.verdict, p.note) for p in mathema.check(fn).probes if p.name in names}
    assert sorted(verdicts) == sorted(names)
    assert {name: v for name, (v, _) in verdicts.items() if v not in ("holds", "proven")} == {}, verdicts
