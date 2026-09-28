# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The README's examples are the shop's real code and verdicts. Every
class and function a python block shows is the one in `examples/shop`,
docstrings aside, and every claim a text block shows (`f = name`, then
the claim, then the verdict with any witness) lands on that verdict,
the witness shown being the start of the one mathema reports."""
import pytest

pytest.importorskip("mathema")
pytest.importorskip("pydantic")
pytest.importorskip("sqlalchemy")
pytest.importorskip("jsonschema")

from mathema.conjecture import check_conjectures, claim  # noqa: E402

from tests._shop_pages import (  # noqa: E402
    ROOT,
    claim_blocks,
    claimed_function,
    definition_problems,
    shop_module,
    witness_matches,
)

README = (ROOT / "README.md").read_text(encoding="utf-8")
MODULES = ("text", "db", "forms", "webhooks", "threads")


def _shop():
    return [shop_module(name) for name in MODULES]


def test_every_definition_shown_is_the_shop_s():
    assert definition_problems(README, _shop()) == []


@pytest.mark.parametrize("fn,text,verdict,witness", claim_blocks(README), ids=lambda v: str(v)[:40])
def test_every_claim_lands_on_its_verdict(fn, text, verdict, witness):
    scope = {k: v for m in reversed(_shop()) for k, v in vars(m).items()}
    target = claimed_function(text, scope, fn)
    (p,) = check_conjectures(target, [claim(text)])
    assert p.verdict == verdict, (text, p.verdict, p.note)
    if witness:
        assert witness_matches(witness, p.counterexample or ""), (witness, p.counterexample)
