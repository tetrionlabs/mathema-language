# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The README's examples are the shop's real code and verdicts. Every
class and function a python block shows is the one in `examples/shop`,
docstrings aside, and every claim a text block shows (`f = name`, then
the claim, then the verdict with any witness) lands on that verdict,
the witness shown being the start of the one mathema reports."""
import ast
import importlib
import pathlib
import re
import sys

import pytest

pytest.importorskip("mathema")
pytest.importorskip("pydantic")
pytest.importorskip("sqlalchemy")
pytest.importorskip("jsonschema")

from mathema.conjecture import check_conjectures, claim  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
MODULES = ("text", "db", "forms", "webhooks", "threads")
_BLOCK = re.compile(r"```(python|text)\n(.*?)```", re.S)
_VERDICT = re.compile(r"^\s+(proven|holds|falsified|unknown|skipped)(?:\s{2,}(.*))?$")


@pytest.fixture(scope="module")
def shop():
    sys.path.insert(0, str(ROOT / "examples"))
    try:
        yield {name: importlib.import_module(f"shop.{name}") for name in MODULES}
    finally:
        sys.path.remove(str(ROOT / "examples"))


def _blocks(kind):
    return [body for k, body in _BLOCK.findall(README) if k == kind]


def _claims():
    out, fn = [], None
    for body in _blocks("text"):
        lines = body.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("f = "):
                fn = line[4:].strip()
            elif line.startswith("for "):
                m = _VERDICT.match(lines[i + 1])
                assert m, line
                out.append((fn, line, m.group(1), m.group(2)))
    return out


def _without_docstrings(node):
    for n in ast.walk(node):
        body = getattr(n, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) \
                and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            n.body = body[1:] or [ast.Pass()]
    return ast.dump(node)


def test_every_definition_shown_is_the_shop_s(shop):
    found = {}
    for module in shop.values():
        for node in ast.parse(pathlib.Path(module.__file__).read_text()).body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                found[node.name] = _without_docstrings(node)
    shown = [n for body in _blocks("python") for n in ast.parse(body).body
             if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
    assert shown
    for node in shown:
        assert _without_docstrings(node) == found.get(node.name), node.name


@pytest.mark.parametrize("fn,text,verdict,witness", _claims(), ids=lambda v: str(v)[:40])
def test_every_claim_lands_on_its_verdict(shop, fn, text, verdict, witness):
    target = next(getattr(m, fn) for m in shop.values() if hasattr(m, fn))
    (p,) = check_conjectures(target, [claim(text)])
    assert p.verdict == verdict, (text, p.verdict, p.note)
    if witness:
        assert (p.counterexample or "").startswith(witness), (witness, p.counterexample)
