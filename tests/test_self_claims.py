# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Claims about this package's own functions, checked by mathema and
pinned: the text vocabulary's normalisers settle, never lengthen where
that is their job, and survive the hazard families; the predicate
languages' membership tests accept their own members and never crash on
arbitrary text; the table vocabulary's empty cases. A falsified row is
a real finding about the function, with its witness pinned. What
mathema could not state about the package is in the task notes, not
forced here."""
import pytest

pytest.importorskip("mathema")

from mathema.conjecture import check_conjectures, claim  # noqa: E402

import mathema_language.text.predicates as predicates  # noqa: E402
import mathema_language.vocabulary._table as table  # noqa: E402
import mathema_language.vocabulary.text as text  # noqa: E402

V = "mathema_language.vocabulary.text"

CLAIMS = [
    # the normalisers settle
    (text.nfc, "for text in L[unicode], f(f(text)) == f(text)", "holds", None),
    (text.nfd, "for text in L[unicode], f(f(text)) == f(text)", "holds", None),
    (text.nfkc, "for text in L[unicode], f(f(text)) == f(text)", "holds", None),
    (text.casefold, "for text in L[unicode], f(f(text)) == f(text)", "holds", None),
    (text.lower, "for text in L[unicode], f(f(text)) == f(text)", "holds", None),
    (text.upper, "for text in L[unicode], f(f(text)) == f(text)", "holds", None),
    (text.strip, "for text in L[unicode], f(f(text)) == f(text)", "holds", None),
    # composition absorbs decomposition, and ASCII is already composed
    (text.nfc, f"let n = {V}.nfd, for text in L[unicode], f(n(text)) == f(text)", "holds", None),
    (text.nfc, "for text in L[ascii], f(text) == text", "holds", None),
    # lengths
    (text.strip, "for text in L[unicode], len(f(text)) <= len(text)", "holds", None),
    (text.upper, "for text in L[unicode], len(f(text)) == len(text)", "falsified", "'ΐ'"),
    (text.nfc_len, "for text in L[unicode], f(text) <= len(text)", "falsified", None),
    (text.count, "for text in L[unicode], part in L[unicode], f(text, part) >= 0", "holds", None),
    (text.count, 'for text in L[unicode], part in L[unicode] \\ {""}, f(text, part) <= len(text)',
     "holds", None),
    (text.startswith, 'for text in L[unicode], f(text, "") == True', "holds", None),
    # the hazard families on the vocabulary
    (text.nfc, "for text in L[unicode], is_arbitrary_input_safe(text)", "holds", None),
    (text.splitlines, "for text in L[unicode], is_arbitrary_input_safe(text)", "holds", None),
    (text.casefold, "for text in L[unicode], is_encoding_safe(text)", "holds", None),
    (text.strip, "for text in L[unicode], is_length_safe(text)", "holds", None),
    # the predicate languages' membership tests
    (predicates._is_slug, "for s in L[slug], f(s) == True", "holds", None),
    (predicates._is_json, "for s in L[json], f(s) == True", "holds", None),
    (predicates._is_json, "for s in L[unicode], is_arbitrary_input_safe(s)", "holds", None),
    (predicates._is_uuid, "for s in L[unicode], is_arbitrary_input_safe(s)", "holds", None),
    (predicates._is_iso_date, "for s in L[unicode], is_arbitrary_input_safe(s)", "holds", None),
    (predicates._is_ipv6, "for s in L[unicode], is_arbitrary_input_safe(s)", "holds", None),
    (predicates._is_base64, "for s in L[unicode], is_arbitrary_input_safe(s)", "holds", None),
    (predicates._is_hex, "for s in L[unicode], is_arbitrary_input_safe(s)", "holds", None),
    (predicates._is_shell_safe, "for s in L[unicode], is_arbitrary_input_safe(s)", "holds", None),
    # the table vocabulary's empty cases
    (table.unique, "f([]) == True", "holds", None),
    (table.rows, "f([]) == 0", "holds", None),
]


@pytest.mark.parametrize("fn, law, verdict, witness", CLAIMS,
                         ids=[f"{fn.__name__}: {law}" for fn, law, _, _ in CLAIMS])
def test_the_claim_lands_on_its_pinned_verdict(fn, law, verdict, witness):
    (p,) = check_conjectures(fn, [claim(law)])
    assert p.verdict == verdict, (p.verdict, p.note, p.counterexample)
    if witness is not None:
        assert witness in str(p.counterexample), p.counterexample


def test_nfc_lengthens_a_composition_exclusion():
    """What the falsified `nfc_len` row found: NFC is not a contraction.
    A character excluded from composition decomposes and stays
    decomposed, so its NFC form is longer."""
    assert len(text.nfc("क़")) == 2
