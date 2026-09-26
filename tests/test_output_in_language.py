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
