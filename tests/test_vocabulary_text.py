# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The text vocabulary: each function does what its name says, carries
a neutral id, and binds into a claim with `let`."""
import textwrap

import pytest

from mathema_language.vocabulary import text as v


def test_normalisation_forms():
    assert v.nfc("é") == "é" and v.nfd("é") == "é"
    assert v.nfkc("ﬁ") == "fi" and v.nfkd("²") == "2"
    assert v.nfc_len("é") == 1


def test_case_and_counting():
    assert v.casefold("ß") == "ss" and v.upper("ß") == "SS"
    assert v.lower("İ") == "i̇"
    assert v.count("a,b,c", ",") == 2
    assert v.startswith("abc", "ab") and v.endswith("abc", "bc")
    strip = v.VOCABULARY["strip"]
    assert strip(" a ") == "a"
    assert v.splitlines("a\nb\r\nc") == ["a", "b", "c"]


def test_every_function_carries_its_id():
    for name, fn in v.VOCABULARY.items():
        assert fn.__mathema_vocabulary__ == f"text.{name}@1"


def test_a_let_bound_vocabulary_function_adjudicates(tmp_path):
    pytest.importorskip("mathema")
    import importlib.util

    from mathema.conjecture import check_conjectures, claim

    p = tmp_path / "vocab_fns.py"
    p.write_text(textwrap.dedent('''
        def collapse(text: str) -> str:
            """Whitespace runs collapsed, ends stripped."""
            return " ".join(text.split())
    '''))
    spec = importlib.util.spec_from_file_location("vocab_fns", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    (r,) = check_conjectures(mod.collapse, [claim(
        "let n = mathema_language.vocabulary.text.nfc, for text in L[unicode], "
        "n(f(text)) == f(n(text))", route="probe")])
    assert r.verdict == "holds", (r.verdict, r.note, r.counterexample)
    assert r.grammar == "mathema/language"
