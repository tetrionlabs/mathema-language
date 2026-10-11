# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""`L[toml]` is the texts that are one TOML document, as the installed
reader reads it: every drawn member reads, the documents code most
often mishandles are its first hazards and all members, the texts no
TOML reader accepts are outside, a document only TOML 1.1 accepts is a
hazard or outside according to the reader's version, each hazard reads
as the page describes it, and `L[toml]` resolves through the package's
entry point."""
import datetime
import math
import random
import sys

import pytest

if sys.version_info < (3, 11):
    pytest.importorskip("tomli")

import mathema.languages as languages  # noqa: E402

from mathema_language.text.toml_language import TOML_TEXT, TOML_VERSION, load  # noqa: E402


def test_it_is_a_language_mathema_accepts_and_resolves_by_name():
    assert languages.language_problems(TOML_TEXT) == []
    assert languages.resolve_language("toml") is TOML_TEXT


def test_every_drawn_document_is_a_member():
    rng = random.Random(4)
    for _ in range(300):
        text = TOML_TEXT.sample(rng)
        assert TOML_TEXT.contains(text), text


def test_the_mishandled_documents_come_first():
    first = [h.value for h in TOML_TEXT.hazards()[:3]]
    assert first == ["released = 2026-10-10\n", "at = 2026-10-10T09:00:00\n",
                     "at = 2026-10-10T09:00:00Z\n"]
    assert all(TOML_TEXT.contains(h.value) for h in TOML_TEXT.hazards())


@pytest.mark.parametrize("text", ["a = 1\na = 2\n", "[a]\nb = 1\n[a]\nc = 2\n", "a = 01\n",
                                  "a = hello\n", "d = 2026-02-30\n", "\ufeffa = 1\n"])
def test_what_no_toml_reader_accepts_is_outside(text):
    assert not TOML_TEXT.contains(text)


@pytest.mark.parametrize("text", ["a = { b = 1, }\n", "a = { b = 1,\n c = 2 }\n", "t = 09:00\n",
                                  'e = "\\e"\n'])
def test_what_only_toml_1_1_accepts_follows_the_reader(text):
    assert TOML_TEXT.contains(text) == (TOML_VERSION == "1.1")


def test_the_toml_1_1_hazards_are_there_only_for_a_1_1_reader():
    hazards = [h.value for h in TOML_TEXT.hazards()]
    assert ("point = { x = 1, y = 2, }\n" in hazards) == (TOML_VERSION == "1.1")


def test_outside_values_are_refused():
    for seed in range(20):
        assert not TOML_TEXT.contains(TOML_TEXT.outside(random.Random(seed)))


def test_the_hazards_read_as_described():
    assert load("released = 2026-10-10\n") == {"released": datetime.date(2026, 10, 10)}
    assert load("at = 2026-10-10T09:00:00\n")["at"].tzinfo is None
    assert load("version = 3.10\n") == {"version": 3.1}
    assert math.isnan(load("ratio = nan\n")["ratio"])
    assert load('server.host = "db"\n') == {"server": {"host": "db"}}
    assert load('"a.b" = 1\n') == {"a.b": 1}
    assert load('s = """\nline"""\n') == {"s": "line"}
    assert load("") == {}
