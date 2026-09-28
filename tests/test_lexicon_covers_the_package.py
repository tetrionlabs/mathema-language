# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The lexicon shows everything the package registers with mathema:
every language, claim family and refinement key it installs appears in
a row, and every adaptor serves at least one row's domain (or, for the
text adaptor, a row's inferred domain), read from the package's own
entry points, so a new registration without an example fails here by
name."""
import importlib.metadata as md
import re
import typing

import pytest

pytest.importorskip("mathema")
pytest.importorskip("pydantic")
pytest.importorskip("sqlalchemy")
pytest.importorskip("django")
pytest.importorskip("jsonschema")

from mathema.conjecture import claim  # noqa: E402
from mathema.domain import LanguageRef  # noqa: E402
from mathema.languages import adapt_annotation, resolve  # noqa: E402

import mathema_language.lexicon as lexicon  # noqa: E402

ROWS = list(lexicon.LEXICON.values())


def _registered(group):
    dist = md.distribution("mathema-language")
    return sorted(ep.name for ep in dist.entry_points if ep.group == group)


@pytest.mark.parametrize("name", _registered("mathema.languages"))
def test_every_language_has_a_row(name):
    assert any(re.search(rf"L\[{re.escape(name)}[\],]", row) for row in ROWS), name


@pytest.mark.parametrize("name", _registered("mathema.claim_families"))
def test_every_family_has_a_row(name):
    assert any(f"{name}(" in row for row in ROWS), name


@pytest.mark.parametrize("key", _registered("mathema.language_refinements"))
def test_every_refinement_key_has_a_row(key):
    assert any(re.search(rf"L\[[^\]]*,\s*{key}\s*(<=|<|>=|>|in)", row) for row in ROWS), key


def _adaptors_used():
    used = set()
    for key, row in lexicon.LEXICON.items():
        cj = claim(row)
        for bound in (cj.domain or {}).values():
            for piece in getattr(bound, "pieces", ()) or ():
                if isinstance(piece, LanguageRef):
                    _, source = resolve(LanguageRef(piece.name))
                    if source.startswith("adaptor "):
                        used.add(source.split()[1])
        if not cj.domain:
            fn = next(f for f, keys in lexicon.EXAMPLE_FUNCTIONS.values() if key in keys)
            for hint in typing.get_type_hints(fn, include_extras=True).values():
                found = adapt_annotation(hint)
                if found is not None and found[1] == "text" and hint is not str:
                    used.add("text")
    return used


@pytest.mark.parametrize("name", _registered("mathema.language_adaptors"))
def test_every_adaptor_serves_a_row(name):
    assert name in _adaptors_used(), name
