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
    "language_retraction": ("falsified", "('NaN'): f returned nan"),
    "language_idempotent": "holds",
    "language_length_bound_identity": "holds",
    "language_length_bound_one_past": ("falsified", "('" + "a" * 81 + "')"),
    "in_target_language": ("falsified", "(''): '' is not in L[slug]"),
    "language_closure_rendered": "holds",
    "language_token_absent": "holds",
    "language_token_present": ("falsified", "('>'): '&' is in f(s)"),
    "record_lift_sign": "proven",
    "record_unbounded_field": ("falsified", "vs 100"),
    "record_length_field": "proven",
    "record_length_field_tight": ("falsified", "10 vs 9"),
    "path_every_element": "holds",
    "path_every_element_unbound": ("falsified", "vs 3"),
    "path_nested_present": "holds",
    "path_nested_missing": ("falsified", "Address(zip=None)"),
    "path_nested_length": "holds",
    "path_nested_length_tight": ("falsified", "5 vs 4"),
    "path_index_present": "holds",
    "path_index_missing": ("falsified", "lines=[]"),
    "structure_induction_constant": "proven",
    "structure_induction_equation": "proven",
    "structure_induction_unbounded": ("falsified", "raised RecursionError"),
    "structure_induction_base_case": ("falsified", "(Branch(label=0, children=[])): 1 vs 2"),
    "structure_depth_bound": "holds",
    "structure_depth_bound_tight": ("falsified", "6 vs 5"),
    "structure_width_bound": "holds",
    "structure_width_one_past": ("falsified", "4 vs 3"),
    "structure_nodes_bound": "holds",
    "structure_json_depth": "holds",
    "language_printable_output": "holds",
    "language_alpha_closure": "holds",
    "language_unicode_alpha_closure": ("falsified", 'is not in L[unicode_alpha]'),
    "language_unicode_alnum_length": "holds",
    "language_identifier_closure": "holds",
    "language_uuid_idempotent": "holds",
    "language_uuid_spelling": ("falsified", "'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'"),
    "language_iso_date_idempotent": "holds",
    "language_iso_datetime_idempotent": "holds",
    "language_ipv4_closure": "holds",
    "language_ipv6_closure": ("falsified", "'::.0' is not in L[ipv6]"),
    "language_base64_round_trip": "holds",
    "language_hex_spelling": ("falsified", "'aa' vs 'aA'"),
    "language_shell_safe_argument": "holds",
    "language_shell_unsafe_argument": ("falsified", "['rm'] vs ['rm', '']"),
    "language_control_header_injection": ("falsified", 'is in f(s)'),
    "language_invisible_blank": ("falsified", 'False vs True'),
    "language_combining_stripped": ("falsified", "vs ''"),
    "language_surrogate_encoding": ("falsified", 'raised UnicodeEncodeError'),
    "language_compatibility_key": ("falsified", "'fi' vs 'ﬁ'"),
    "language_astral_utf16": "holds",
    "family_excluded_outside_domain": "holds",
    "family_excluded_outside_domain_accepts": ("falsified", '(outside L[ascii] at [0]: ascii alphabet)'),
    "vocabulary_tree_depth": "holds",
    "adaptor_text_annotation": "holds",
    "adaptor_pydantic_proven": "proven",
    "adaptor_pydantic_falsified": ("falsified", '5 vs 4'),
    "adaptor_sqlalchemy_proven": "proven",
    "adaptor_sqlalchemy_falsified": ("falsified", 'vs 10000'),
    "adaptor_django_proven": "proven",
    "adaptor_django_falsified": ("falsified", '0.2 vs 0.5'),
    "adaptor_jsonschema_proven": "proven",
    "adaptor_jsonschema_falsified": ("falsified", 'raised KeyError'),
    "adaptor_typeddict_proven": "proven",
    "adaptor_typeddict_falsified": ("falsified", 'vs 10'),
    "family_length_safe": "holds",
    "family_encoding_safe": ("falsified", "raised UnicodeEncodeError"),
    "family_arbitrary_input": ("falsified", "s = '' (inside L[unicode]) raised IndexError"),
    "closure_ascii_in_ascii_out": "holds",
    "closure_ascii_leaves": ("falsified", "is not in L[ascii]"),
}


def test_the_lexicon_passes_every_check_mathema_s_own_does():
    problems = lexicon_problems(SOURCE, golden=str(GOLDEN), expected=EXPECTED)
    assert problems == {}, "\n".join(f"{check}:\n  " + "\n  ".join(found)
                                     for check, found in problems.items())


@pytest.mark.parametrize("key", list(lexicon.LEXICON))
def test_every_row_is_in_the_language_dialect_and_its_domain_round_trips(key):
    cj = claim(lexicon.LEXICON[key])
    # a row that writes no domain shows one inferred from the function's
    # annotation, and is in the dialect only once the function is known
    assert cj.grammar == "mathema/language" or not cj.domain
    for bound in cj.domain.values():
        assert domain_bound_from_json(domain_bound_to_json(bound)) == bound


def test_installed_the_rows_join_mathema_s_lexicon():
    import mathema.lexicon as core
    assert core.origin("language_idempotent") == "language"
    assert "language_idempotent" in core.entries("language/laws")
    assert "language_idempotent" not in core.LEXICON


#: the route each proven row is proven on
PROVEN_ROUTES = {
    "record_lift_sign": "derive",
    "record_length_field": "derive",
    "adaptor_pydantic_proven": "derive",
    "adaptor_sqlalchemy_proven": "derive",
    "adaptor_django_proven": "derive",
    "adaptor_jsonschema_proven": "derive",
    "adaptor_typeddict_proven": "derive",
    "structure_induction_constant": "derive:induction",
    "structure_induction_equation": "derive:induction",
}


def test_a_proven_row_is_proven_by_derive():
    from mathema.conjecture import check_conjectures
    proven = {key for key, want in EXPECTED.items() if want == "proven"}
    assert proven == set(PROVEN_ROUTES)
    for fn, keys in lexicon.EXAMPLE_FUNCTIONS.values():
        for key in keys:
            if key in proven:
                (p,) = check_conjectures(fn, [claim(lexicon.LEXICON[key])])
                assert (p.verdict, p.route) == ("proven", PROVEN_ROUTES[key]), \
                    (key, p.verdict, p.route)
