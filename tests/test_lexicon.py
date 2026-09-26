# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Every worked claim in this package's lexicon parses under mathema's
grammar, its language resolves through the entry point, its domain
round-trips through mathema's JSON codec, and it adjudicates against
its example function without raising."""
import pytest

pytest.importorskip("mathema")

from mathema.conjecture import check_conjectures, claim  # noqa: E402
from mathema.domain import domain_bound_from_json, domain_bound_to_json  # noqa: E402

from mathema_language.lexicon import EXAMPLE_FUNCTIONS, LEXICON  # noqa: E402


@pytest.mark.parametrize("key", list(LEXICON))
def test_every_entry_parses_and_its_domain_round_trips(key):
    cj = claim(LEXICON[key])
    assert cj.grammar == "mathema/language"
    for bound in cj.domain.values():
        assert domain_bound_from_json(domain_bound_to_json(bound)) == bound


def test_every_key_has_an_example_function():
    covered = {key for _, keys in EXAMPLE_FUNCTIONS.values() for key in keys}  # noqa: PERF102
    assert covered == set(LEXICON)


@pytest.mark.parametrize("name", list(EXAMPLE_FUNCTIONS))
def test_example_functions_adjudicate_their_keys(name):
    fn, keys = EXAMPLE_FUNCTIONS[name]
    for key in keys:
        (p,) = check_conjectures(fn, [claim(LEXICON[key], route="probe")])
        assert p.verdict in ("holds", "proven", "falsified"), (key, p.verdict, p.note)
        assert p.meta["mathema.language"]
