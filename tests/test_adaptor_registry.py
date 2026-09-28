# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The adaptors are ordinary registrations. Every one registered under
`mathema.language_adaptors`, from this package or another, returns None
for objects that are not its own without importing its library
(checked in a fresh interpreter, so a library imported by an earlier
test cannot hide it). They are asked in mathema's order,
library-specific before document before structural, and an adaptor
another package registers is found by `adapt_row` and passes the same
conformance checks."""
import json
import subprocess
import sys
from importlib.metadata import entry_points

import pytest

pytest.importorskip("mathema")

import mathema.languages as languages  # noqa: E402

from mathema_language.conformance import row_adaptor_problems  # noqa: E402
from mathema_language.schema import PlainEcosystem, RowLanguage  # noqa: E402
from mathema_language.schema.adaptors import adapt_row  # noqa: E402
from mathema_language.schema.model import Field, NeutralType, RowSchema  # noqa: E402

GROUP = "mathema.language_adaptors"
REGISTERED = sorted(ep.name for ep in entry_points(group=GROUP))

_PROBE = """
import json, sys
from importlib.metadata import entry_points
from mathema_language.conformance import FOREIGN, foreign_object_problems
(ep,) = [e for e in entry_points(group="mathema.language_adaptors") if e.name == sys.argv[1]]
adapt = ep.load()
foreign = tuple(x for x in FOREIGN if x is not str) if sys.argv[1] == "text" else FOREIGN
print(json.dumps(foreign_object_problems(adapt)
                 if sys.argv[1] != "text" else foreign_object_problems(adapt, foreign=foreign)))
"""


@pytest.mark.parametrize("name", REGISTERED)
def test_every_registered_adaptor_returns_none_for_other_objects_without_importing_its_library(name):
    done = subprocess.run([sys.executable, "-c", _PROBE, name], capture_output=True, text=True,
                          check=True)
    assert json.loads(done.stdout.strip().splitlines()[-1]) == [], (name, done.stdout)


def test_the_package_s_adaptors_are_asked_library_first():
    ours = [name for name, _ in languages.language_adaptors()
            if name in {"django", "pydantic", "sqlalchemy", "jsonschema",
                        "dataclass", "text", "typeddict"}]
    assert ours == ["django", "pydantic", "sqlalchemy", "jsonschema",
                    "dataclass", "text", "typeddict"]


class Marker:
    """A schema class of an imaginary library."""


def third_party_adapt(obj):
    """The third party's adaptor: a row language for `Marker`."""
    if obj is not Marker:
        return None
    schema = RowSchema("Marker", (Field("n", NeutralType("int")),))
    return RowLanguage(schema, PlainEcosystem(), "Marker")


third_party_adapt.__mathema_adaptor_priority__ = 100


class _Entry:
    def __init__(self, name, obj):
        self.name, self.value, self._obj = name, f"thirdparty:{name}", obj

    def load(self):
        return self._obj


def test_an_adaptor_from_another_package_is_found_and_passes_the_checks(monkeypatch):
    discovered = languages._discovered_adaptors()
    monkeypatch.setattr(languages, "_discovered_adaptors",
                        lambda: (*discovered, _Entry("marker", third_party_adapt)))
    languages._loaded_adaptors.cache_clear()
    try:
        assert adapt_row(Marker).name == "Marker"
        assert row_adaptor_problems(Marker, adapt=third_party_adapt) == []
    finally:
        languages._loaded_adaptors.cache_clear()
