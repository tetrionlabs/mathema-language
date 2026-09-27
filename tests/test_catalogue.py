# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The claim catalogue runs: every python block on the page defines its
section's functions, and every table row's claim lands on the verdict
the page prints beside it."""
import importlib.util
import pathlib
import re
import sys

import pytest

pytest.importorskip("mathema")

from mathema.conjecture import check_conjectures, claim  # noqa: E402

DOC = pathlib.Path(__file__).resolve().parents[1] / "docs" / "catalogue.md"
_BLOCK = re.compile(r"```python\n(.*?)```", re.S)
_ROW = re.compile(r"^\| `([^`]+)` \| `(.+?)` \| (\w+) \|", re.M)


def _sections():
    """`(title, code, rows)` per section that has both a code block
    and a claim table; the renderer section reuses the parser's code."""
    text = DOC.read_text(encoding="utf-8")
    code = ""
    for part in re.split(r"^## ", text, flags=re.M)[1:]:
        title = part.splitlines()[0].strip()
        blocks = _BLOCK.findall(part)
        if blocks:
            code = "\n".join(blocks)
        rows = _ROW.findall(part)
        if rows:
            yield title, code, rows


def _module(tmp_path, title, code):
    slug = re.sub(r"\W+", "_", title.lower()).strip("_")
    path = tmp_path / f"catalogue_{slug}.py"
    path.write_text(code, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(f"catalogue_{slug}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


CASES = [(title, code, fn, law, verdict)
         for title, code, rows in _sections() for fn, law, verdict in rows]


@pytest.mark.parametrize(
    "title,code,fn_name,law,verdict", CASES,
    ids=[f"{t}:{f}:{law[:48]}" for t, _, f, law, _ in CASES])
def test_every_catalogue_row_lands_on_its_printed_verdict(tmp_path, title, code,
                                                         fn_name, law, verdict):
    mod = _module(tmp_path, title, code)
    (p,) = check_conjectures(getattr(mod, fn_name), [claim(law, route="best")])
    assert p.verdict == verdict, (p.verdict, p.route, p.note, p.counterexample)


def test_the_catalogue_covers_every_nature():
    titles = {title for title, _, _ in _sections()}
    assert {"Parser", "Renderer", "Normaliser", "Validator", "Escaper", "Consumer", "Row"} <= titles
    assert len(CASES) >= 20
