# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""`is_encoding_safe(s)`: the control and format code points, the
combining marks, the surrogates, the length-changing characters and
the member past every codec the body names reach the body; an
unguarded UnicodeError or other accidental crash falsifies with a
witness naming the character and its category, and a guarded body
holds."""
import textwrap

import pytest

pytest.importorskip("mathema")

from mathema.conjecture import check_conjectures, claim  # noqa: E402


def _load(tmp_path, body, name="encoding_fns"):
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


def test_an_unguarded_codec_boundary_falsifies_naming_the_character(tmp_path):
    mod = _load(tmp_path, '''
        def wire(s: str) -> bytes:
            """The text on the wire, as ascii."""
            return s.encode("ascii")
    ''')
    p = _one(mod.wire, "for s in L[unicode], is_encoding_safe(s)")
    assert p.verdict == "falsified", (p.verdict, p.note)
    assert "UnicodeEncodeError" in p.counterexample
    assert "category" in p.counterexample and "inside L[unicode]" in p.counterexample


def test_a_lone_surrogate_reaches_utf8(tmp_path):
    mod = _load(tmp_path, '''
        def wire(s: str) -> bytes:
            """The text on the wire, as utf-8."""
            return s.encode("utf-8")
    ''')
    p = _one(mod.wire, "for s in L[unicode], is_encoding_safe(s)")
    assert p.verdict == "falsified", (p.verdict, p.note)
    assert "SURROGATE" in p.counterexample or "\\ud8" in p.counterexample


def test_a_guarded_body_holds(tmp_path):
    mod = _load(tmp_path, '''
        def wire(s: str) -> bytes:
            """The text on the wire, as ascii, or a rejection."""
            if not s.isascii():
                raise ValueError("ascii only")
            return s.encode("ascii")
    ''')
    p = _one(mod.wire, "for s in L[unicode], is_encoding_safe(s)")
    assert p.verdict == "holds", (p.verdict, p.note, p.counterexample)


def test_inside_a_narrow_language_the_boundary_is_not_a_member(tmp_path):
    mod = _load(tmp_path, '''
        def wire(s: str) -> bytes:
            """The text on the wire, as ascii."""
            return s.encode("ascii")
    ''')
    p = _one(mod.wire, "for s in L[ascii], is_encoding_safe(s)")
    assert p.verdict == "holds", (p.verdict, p.note, p.counterexample)
