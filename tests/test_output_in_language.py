# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""`output_in_language(f(s))`: every output is a member of the target
language, which is the language the first text parameter is declared
over, else the language the return annotation adapts to, else every
`str`; the witness names the target and how it was chosen."""
import textwrap

import pytest

pytest.importorskip("mathema")

from mathema.conjecture import check_conjectures, claim  # noqa: E402


def _load(tmp_path, body, name="closure_fns"):
    import importlib.util
    p = tmp_path / f"{name}.py"
    p.write_text(textwrap.dedent(body))
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _one(fn, law):
    (p,) = check_conjectures(fn, [claim(law, route="best")])
    return p


def test_closure_into_the_declared_language_holds(tmp_path):
    mod = _load(tmp_path, '''
        def shout(s: str) -> str:
            """Upper case."""
            return s.upper()
    ''')
    p = _one(mod.shout, "for s in L[ascii], output_in_language(f(s))")
    assert p.verdict == "holds", (p.verdict, p.note, p.counterexample)
    assert p.grammar == "mathema/language"


def test_an_output_that_leaves_the_language_falsifies_naming_the_target(tmp_path):
    mod = _load(tmp_path, '''
        def accent(s: str) -> str:
            """An accent appended."""
            return s + "\\u00e9"
    ''')
    p = _one(mod.accent, "for s in L[ascii], output_in_language(f(s))")
    assert p.verdict == "falsified", (p.verdict, p.note)
    assert "not in L[ascii]" in p.counterexample
    assert "the language s is declared over" in p.counterexample
    assert "LATIN SMALL LETTER E WITH ACUTE" in p.counterexample, p.counterexample


def test_a_non_string_output_is_not_a_member(tmp_path):
    mod = _load(tmp_path, '''
        def size(s: str) -> int:
            """The length."""
            return len(s)
    ''')
    p = _one(mod.size, "for s in L[ascii], output_in_language(f(s))")
    assert p.verdict == "falsified", (p.verdict, p.note)
    assert "not in L[ascii]" in p.counterexample


def test_with_no_declared_language_the_return_annotation_decides(tmp_path):
    mod = _load(tmp_path, '''
        def wrap(s: str) -> str:
            """Wrapped in brackets."""
            return "[" + s + "]"
    ''')
    p = _one(mod.wrap, "output_in_language(f(s))")
    assert p.verdict == "holds", (p.verdict, p.note, p.counterexample)
    assert claim("output_in_language(f(s))").relation == "output_in_language"


def test_the_record_names_the_target_and_where_it_came_from(tmp_path):
    mod = _load(tmp_path, '''
        def shout(s: str) -> str:
            """Upper case."""
            return s.upper()
    ''')
    p = _one(mod.shout, "for s in L[ascii], output_in_language(f(s))")
    assert p.verdict == "holds", (p.verdict, p.note)
    described = p.meta["mathema.language"]
    assert described["return"] == [{"name": "ascii", "from": "parameter s"}]
    assert described["s"][0]["name"] == "ascii"


def test_a_falsified_record_names_the_target_too(tmp_path):
    mod = _load(tmp_path, '''
        def accent(s: str) -> str:
            """An accent appended."""
            return s + "\\u00e9"
    ''')
    p = _one(mod.accent, "for s in L[ascii], output_in_language(f(s))")
    assert p.verdict == "falsified", (p.verdict, p.note)
    assert p.meta["mathema.language"]["return"] == [{"name": "ascii", "from": "parameter s"}]


def test_a_union_of_languages_names_each_target(tmp_path):
    mod = _load(tmp_path, '''
        def same(s: str) -> str:
            """The input."""
            return s
    ''')
    p = _one(mod.same, "for s in L[digit] | L[ascii], output_in_language(f(s))")
    assert p.verdict == "holds", (p.verdict, p.note)
    assert p.meta["mathema.language"]["return"] == [
        {"name": "digit", "from": "parameter s"}, {"name": "ascii", "from": "parameter s"}]


def test_the_return_annotation_is_named_when_it_decides(tmp_path):
    mod = _load(tmp_path, '''
        def count(n: int) -> str:
            """The number as text."""
            return str(n)
    ''')
    p = _one(mod.count, "for n in [0, 100], output_in_language(f(n))")
    assert p.verdict == "holds", (p.verdict, p.note)
    assert p.meta["mathema.language"]["return"] == [
        {"name": "unicode", "from": "return annotation str"}]
    assert set(p.meta["mathema.language"]) == {"return"}
