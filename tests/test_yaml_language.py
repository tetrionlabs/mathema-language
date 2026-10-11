# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""`L[yaml]` is the texts that are one YAML document, read as YAML 1.2:
every drawn member loads, the documents a YAML 1.1 reader misreads are
its first hazards and all members, the texts no YAML reader accepts are
outside, and `L[yaml]` resolves through the package's entry point."""
import random

import pytest

pytest.importorskip("ruamel.yaml")

import mathema.languages as languages  # noqa: E402

from mathema_language.text.yaml_language import YAML_TEXT, load  # noqa: E402


def test_it_is_a_language_mathema_accepts_and_resolves_by_name():
    assert languages.language_problems(YAML_TEXT) == []
    assert languages.resolve_language("yaml") is YAML_TEXT


def test_every_drawn_document_is_a_member():
    rng = random.Random(4)
    for _ in range(300):
        text = YAML_TEXT.sample(rng)
        assert YAML_TEXT.contains(text), text


def test_the_misread_documents_come_first():
    first = [h.value for h in YAML_TEXT.hazards()[:4]]
    assert first == ["country: no\n", "on: push\n", "python: 3.10\n", "mode: 012\n"]
    assert all(YAML_TEXT.contains(h.value) for h in YAML_TEXT.hazards())


@pytest.mark.parametrize("text", ["a:\n\tb: 1\n", "a: 1\na: 2\n", "a: b: c\n", "key: [1, 2\n",
                                  "a: 1\n---\nb: 2\n"])
def test_what_no_yaml_reader_accepts_is_outside(text):
    assert not YAML_TEXT.contains(text)


def test_outside_values_are_refused():
    for seed in range(20):
        assert not YAML_TEXT.contains(YAML_TEXT.outside(random.Random(seed)))


def test_the_reference_reading_is_yaml_1_2_where_pyyaml_reads_1_1():
    yaml = pytest.importorskip("yaml")
    for text, v12, v11 in [("country: no", {"country": "no"}, {"country": False}),
                           ("mode: 012", {"mode": 12}, {"mode": 10}),
                           ("t: 1:20", {"t": "1:20"}, {"t": 80})]:
        assert load(text) == v12
        assert yaml.safe_load(text) == v11
