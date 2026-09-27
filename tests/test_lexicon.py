# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""This package's lexicon is held to exactly the checks mathema holds
its own to, by mathema's own code (`lexicon_problems` on the extension
surface), against this package's golden snapshot
(`data/lexicon_golden.json`) and the verdicts pinned here: every row
parses and renders in both forms, matches the snapshot, is a fixed
point of render and parse in both modes with a stable canonical form
that reaches the same verdict, survives the declared store and the
verified record, states its missing-value policy, sits in exactly one
section, is found by one of its tags, has an example function, and
lands on its pinned verdict (and witness, where falsified). Installed,
the rows join mathema's own through the `mathema.lexicon` entry point.

When a row or a rendering changes on purpose, regenerate the snapshot
and review the diff:

    python -c "from mathema_language._surface import lexicon_source, \\
        write_lexicon_golden; import mathema_language.lexicon as m; \\
        write_lexicon_golden(lexicon_source('language', m), \\
        'tests/data/lexicon_golden.json')"
"""
import pathlib

import pytest

pytest.importorskip("mathema")

from mathema.conjecture import claim  # noqa: E402
from mathema.domain import domain_bound_from_json, domain_bound_to_json  # noqa: E402

import mathema_language.lexicon as lexicon  # noqa: E402
from mathema_language._surface import lexicon_problems, lexicon_source  # noqa: E402

GOLDEN = pathlib.Path(__file__).parent / "data" / "lexicon_golden.json"
SOURCE = lexicon_source("language", lexicon)

#: every row's verdict against its example function, and a text the
#: witness contains where it is falsified
EXPECTED = {
    "language_with_special_member": "holds",
    "language_homomorphism": "holds",
    "language_encoding_boundary": ("falsified", "raised UnicodeEncodeError"),
    "language_section_inverse": "holds",
    "language_retraction": "holds",
    "language_idempotent": "holds",
    "language_length_bound_identity": "holds",
    "language_length_bound_one_past": ("falsified", " vs "),
    "language_closure_into_another": ("falsified", "'' is not in L[slug]"),
    "language_closure_rendered": "holds",
    "language_token_absent": "holds",
    "language_token_present": ("falsified", "'&' is in f(s)"),
    "row_lift_sign": "proven",
    "row_unbounded_field": ("falsified", "vs 100"),
    "row_length_field": "proven",
    "row_length_field_tight": ("falsified", "10 vs 9"),
    "family_length_safe": "holds",
    "family_encoding_safe": ("falsified", "raised UnicodeEncodeError"),
    "family_arbitrary_input": ("falsified", "s = '' (inside L[unicode]) raised IndexError"),
    "family_output_in_language": "holds",
    "family_output_leaves_language": ("falsified", "output 'é' is not in L[ascii]"),
}


def test_the_lexicon_passes_every_check_mathema_s_own_does():
    problems = lexicon_problems(SOURCE, golden=str(GOLDEN), expected=EXPECTED)
    assert problems == {}, "\n".join(f"{check}:\n  " + "\n  ".join(found)
                                     for check, found in problems.items())


@pytest.mark.parametrize("key", list(lexicon.LEXICON))
def test_every_row_is_in_the_language_dialect_and_its_domain_round_trips(key):
    cj = claim(lexicon.LEXICON[key])
    assert cj.grammar == "mathema/language"
    for bound in cj.domain.values():
        assert domain_bound_from_json(domain_bound_to_json(bound)) == bound


def test_installed_the_rows_join_mathema_s_lexicon():
    import mathema.lexicon as core
    assert core.origin("language_idempotent") == "language"
    assert "language_idempotent" in core.entries("language/laws")
    assert "language_idempotent" not in core.LEXICON


def test_a_proven_row_is_proven_by_derive():
    from mathema.conjecture import check_conjectures
    for fn, keys in lexicon.EXAMPLE_FUNCTIONS.values():
        for key in keys:
            if EXPECTED[key] == "proven":
                (p,) = check_conjectures(fn, [claim(lexicon.LEXICON[key])])
                assert (p.verdict, p.route) == ("proven", "derive"), (key, p.verdict, p.route)
