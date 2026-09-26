# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The text hazard corpus: every entry has a known kind, the corpus is
deduplicated, and the length-changing characters it carries do change
length under the transforms real code applies."""
import unicodedata

from mathema_language._surface import HAZARD_KINDS
from mathema_language.text.hazards import TEXT_HAZARDS


def test_every_hazard_has_a_known_kind_and_a_note():
    for hazard in TEXT_HAZARDS:
        assert hazard.kind in HAZARD_KINDS, hazard
        assert hazard.note


def test_the_corpus_is_deduplicated():
    values = [h.value for h in TEXT_HAZARDS]
    assert len(values) == len(set(values))


def test_the_control_prefix_holds_every_c0_code_point():
    prefix = next(h.value for h in TEXT_HAZARDS if "C0" in h.note)
    assert prefix == "".join(chr(c) for c in range(0x21))


def test_length_changing_characters_change_length():
    assert len("ß".upper()) == 2
    assert len("İ".lower()) == 2
    assert len("ﬁ".upper()) == 2
    assert len("ΐ".upper()) == 3
    assert len(unicodedata.normalize("NFKC", "ﬁ")) == 2
    assert len(unicodedata.normalize("NFC", "é")) == 1
    assert len(unicodedata.normalize("NFD", "é")) == 2
    corpus = {h.value for h in TEXT_HAZARDS}
    assert {"ß", "İ", "ﬁ", "ΐ", "é"} <= corpus


def test_the_pathological_inputs_are_long_but_bounded():
    lengths = [len(h.value) for h in TEXT_HAZARDS if h.kind == "length"]
    assert lengths and max(lengths) <= 65536
