# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""`is_length_safe(s)`: the long and pathological members of the
declared language reach the body; an unguarded crash on one falsifies
with a shrunk witness that stays inside the language, a body that
copes holds, and the postfix spelling reparses."""
import textwrap

import pytest

pytest.importorskip("mathema")

from mathema.conjecture import check_conjectures, claim  # noqa: E402


def _load(tmp_path, body, name="length_fns"):
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


def test_an_unguarded_crash_on_a_long_member_falsifies(tmp_path):
    mod = _load(tmp_path, '''
        def depth(s: str) -> int:
            """The nesting depth, counted recursively."""
            if not s:
                return 0
            return depth(s[1:]) + (1 if s[0] == "(" else 0)
    ''')
    p = _one(mod.depth, "for s in L[ascii], is_length_safe(s)")
    assert p.verdict == "falsified", (p.verdict, p.note)
    assert "RecursionError" in p.counterexample and "inside L[ascii]" in p.counterexample
    assert p.route == "probe:minimal_example"


def test_a_body_that_copes_holds(tmp_path):
    mod = _load(tmp_path, '''
        def depth(s: str) -> int:
            """The nesting depth, counted with a loop."""
            level = best = 0
            for ch in s:
                level += 1 if ch == "(" else -1 if ch == ")" else 0
                best = max(best, level)
            return best
    ''')
    p = _one(mod.depth, "for s in L[ascii], is_length_safe(s)")
    assert p.verdict == "holds", (p.verdict, p.note, p.counterexample)


def test_a_deliberate_rejection_is_not_a_crash(tmp_path):
    mod = _load(tmp_path, '''
        def bounded(s: str) -> int:
            """Refuses anything past a kibibyte."""
            if len(s) > 1024:
                raise ValueError("too long")
            return len(s)
    ''')
    p = _one(mod.bounded, "for s in L[unicode], is_length_safe(s)")
    assert p.verdict == "holds", (p.verdict, p.note)


def test_the_postfix_spelling_and_the_undeclared_language(tmp_path):
    cj = claim("s is length safe")
    assert cj.relation == "is_length_safe" and cj.lhs == "s"
    mod = _load(tmp_path, '''
        def depth(s: str) -> int:
            """The nesting depth, counted recursively."""
            if not s:
                return 0
            return depth(s[1:]) + 1
    ''')
    p = _one(mod.depth, "is_length_safe(s)")
    assert p.verdict == "falsified" and "inside L[unicode]" in p.counterexample
