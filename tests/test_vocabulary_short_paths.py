# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The vocabulary is bound by a short path, `let nfkc =
mathema_language.text.nfkc` and `let depth = mathema_language.tree.depth`,
the same functions with the same identifiers as their home modules."""
import pytest

pytest.importorskip("mathema")

from mathema.conjecture import check_conjectures, claim  # noqa: E402

import mathema_language.text as text  # noqa: E402
import mathema_language.tree as tree  # noqa: E402
from mathema_language.vocabulary import text as text_vocabulary  # noqa: E402
from mathema_language.vocabulary import tree as tree_vocabulary  # noqa: E402


def test_every_function_has_a_short_path():
    for name, fn in text_vocabulary.VOCABULARY.items():
        assert getattr(text, name) is fn and fn.__mathema_vocabulary__ == f"text.{name}@1"
    for name, fn in tree_vocabulary.VOCABULARY.items():
        assert getattr(tree, name) is fn and fn.__mathema_vocabulary__ == f"tree.{name}@1"


def shout(s: str) -> str:
    """Upper case."""
    return s.upper()


def test_a_claim_binds_the_short_path():
    (p,) = check_conjectures(shout, [claim(
        "let nfkc = mathema_language.text.nfkc, for s in L[ascii], nfkc(shout(s)) == shout(s)")])
    assert p.verdict == "holds", (p.verdict, p.note)
