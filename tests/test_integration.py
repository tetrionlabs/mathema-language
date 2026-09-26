# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Everything that needs a live mathema goes here: the entry points are
discovered, a name resolves from them, a claim over a language holds
with the dialect stamp and the record naming this package, an encoding
boundary falsifies with the member as witness, and an unknown name is
still refused."""
import textwrap
from importlib.metadata import entry_points

import pytest

pytest.importorskip("mathema")

import pathlib  # noqa: E402

try:
    import tomllib
except ImportError:                       # Python 3.10
    tomllib = pytest.importorskip("tomli")

from mathema.conjecture import check_conjectures, claim  # noqa: E402
from mathema.domain import LanguageRef  # noqa: E402
from mathema.languages import UnknownLanguage, resolve  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load(tmp_path, body, name="lang_pkg_fns"):
    import importlib.util
    p = tmp_path / f"{name}.py"
    p.write_text(textwrap.dedent(body))
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_entry_points_match_the_pyproject_table():
    declared = tomllib.loads((ROOT / "pyproject.toml").read_text())
    table = declared["project"]["entry-points"]["mathema.languages"]
    discovered = {ep.name: ep.value for ep in entry_points(group="mathema.languages")
                  if ep.value.startswith("mathema_language")}
    assert discovered == table


def test_a_name_resolves_from_the_entry_point():
    language, source = resolve(LanguageRef("ascii"))
    assert language.name == "ascii"
    assert source.startswith("entry point mathema_language")


def test_a_claim_over_a_language_holds_with_the_dialect_and_the_source(tmp_path):
    mod = _load(tmp_path, '''
        def shout(s: str) -> str:
            """Upper case."""
            return s.upper()
    ''')
    (p,) = check_conjectures(mod.shout, [claim("for s in L[ascii], len(f(s)) == len(s)")])
    assert p.verdict == "holds", (p.verdict, p.note, p.counterexample)
    assert p.grammar == "mathema/language"
    assert p.meta["mathema.language"]["s"][0]["source"].startswith("entry point")


def test_an_encoding_boundary_falsifies_with_the_member_as_witness(tmp_path):
    mod = _load(tmp_path, '''
        def ascii_only(s: str) -> str:
            """The text, if ascii."""
            return s.encode("ascii").decode("ascii")
    ''')
    (p,) = check_conjectures(mod.ascii_only, [claim("for s in L[latin-1], f(s) == s")])
    assert p.verdict == "falsified" and "UnicodeEncodeError" in p.counterexample
    (q,) = check_conjectures(mod.ascii_only, [claim("for s in L[ascii], f(s) == s")])
    assert q.verdict == "holds"


def test_upper_case_is_not_length_preserving_over_unicode(tmp_path):
    mod = _load(tmp_path, '''
        def shout(s: str) -> str:
            """Upper case."""
            return s.upper()
    ''')
    (p,) = check_conjectures(mod.shout, [claim("for s in L[unicode], len(f(s)) == len(s)")])
    assert p.verdict == "falsified", (p.verdict, p.note)


def test_an_unknown_name_is_still_refused():
    with pytest.raises(UnknownLanguage, match="L\\[nope\\]"):
        resolve(LanguageRef("nope"))
