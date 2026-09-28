# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Every reference page runs. A page marked `<!-- shop: db forms -->`
draws its examples from those modules of `examples/shop`: the code it
shows is the shop's own, its other python blocks run with the shop's
names in scope, and its claims name the shop (`L[shop.db.Order]`).
Otherwise a page's python blocks are one module,
named by the page's `<!-- module: NAME -->` marker and importable under
that name, so a claim on the page can write `L[NAME.Line]`; a text block
marked `<!-- output -->` is what the python block before it prints, and
must be exactly that; every claim row (`| fn | claim | verdict |`) lands
on its printed verdict; a page marked `<!-- requires: MODULE -->` skips
when MODULE is not installed. The catalogue has its own test; every
page named in `reference.yml` exists, every page in `docs/` is named
there, and every relative link between pages resolves."""
import importlib.util
import pathlib
import re
import sys

import pytest

pytest.importorskip("mathema")

from mathema.conjecture import check_conjectures, claim  # noqa: E402

from tests._shop_pages import (  # noqa: E402
    blocks,
    claim_blocks,
    claim_rows,
    definition_problems,
    is_shown_code,
    shop_module,
    witness_matches,
)

DOCS = pathlib.Path(__file__).resolve().parents[1] / "docs"
_FENCE = re.compile(r"(<!-- output -->\n)?```(python|text)\n(.*?)```", re.S)
_ROW = re.compile(r"^\| `([^`]+)` \| `(.+?)` \| (\w+) \|", re.M)
_SENTINEL = "\x1e"


def _pages():
    return sorted(p for p in DOCS.glob("*.md") if p.name != "catalogue.md")


def _module(page, tmp_path):
    """The page's module and what each python block printed."""
    text = page.read_text(encoding="utf-8")
    for needed in re.findall(r"<!-- requires: (\w+) -->", text):
        pytest.importorskip(needed)
    name = re.search(r"<!-- module: (\w+) -->", text)
    if name is None:
        return None, [], text
    blocks, expected = [], []
    for marker, kind, body in _FENCE.findall(text):
        if kind == "python":
            blocks.append(body)
            expected.append(None)
        elif marker:
            expected[-1] = body
    source = "".join(f"{body}\nprint({_SENTINEL!r})\n" for body in blocks)
    path = tmp_path / f"{name.group(1)}.py"
    path.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(name.group(1), path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name.group(1)] = mod
    return mod, expected, text


@pytest.mark.parametrize("page", _pages(), ids=lambda p: p.stem)
def test_the_page_runs_and_prints_what_it_shows(page, tmp_path, capsys):
    mod, expected, text = _module(page, tmp_path)
    if mod is None:
        return
    mod.__spec__.loader.exec_module(mod)
    printed = capsys.readouterr().out.split(_SENTINEL + "\n")
    for i, shown in enumerate(expected):
        if shown is not None:
            assert printed[i].rstrip("\n") == shown.rstrip("\n"), (page.name, i, printed[i])
    for fn, law, verdict in _ROW.findall(text):
        (p,) = check_conjectures(getattr(mod, fn), [claim(law, route="best")])
        assert p.verdict == verdict, (page.name, law, p.verdict, p.note, p.counterexample)


def test_the_reference_nav_names_every_page():
    listed = re.findall(r":\s*([\w-]+\.md)\s*$", (DOCS / "reference.yml").read_text(), re.M)
    assert sorted(listed) == sorted(p.name for p in DOCS.glob("*.md"))


def test_every_relative_link_resolves():
    for page in DOCS.glob("*.md"):
        for target in re.findall(r"\]\(([\w-]+\.md)(?:#[\w-]+)?\)", page.read_text()):
            assert (DOCS / target).exists(), (page.name, target)


def _shop_pages():
    return [p for p in _pages() if "<!-- shop:" in p.read_text(encoding="utf-8")]


@pytest.mark.parametrize("page", _shop_pages(), ids=lambda p: p.stem)
def test_a_shop_page_shows_the_shop_and_its_claims_land(page, capsys):
    text = page.read_text(encoding="utf-8")
    for needed in re.findall(r"<!-- requires: (\w+) -->", text):
        pytest.importorskip(needed)
    names = re.search(r"<!-- shop: ([\w ]+) -->", text).group(1).split()
    modules = [shop_module(name) for name in names]
    assert definition_problems(text, modules) == [], page.name
    scope: dict = {}
    for module in modules:
        scope.update(vars(module))
    shown = None
    for kind, body, is_output in blocks(text):
        if kind == "python" and not is_shown_code(body):
            exec(compile(body, page.name, "exec"), scope)  # noqa: S102
            shown = capsys.readouterr().out
        elif kind == "text" and is_output:
            assert shown is not None and shown.rstrip("\n") == body.rstrip("\n"), (page.name, shown)
    for fn, law, verdict in claim_rows(text):
        (p,) = check_conjectures(scope[fn], [claim(law, route="best")])
        assert p.verdict == verdict, (page.name, law, p.verdict, p.note, p.counterexample)
    for fn, law, verdict, witness in claim_blocks(text):
        (p,) = check_conjectures(scope[fn], [claim(law)])
        assert p.verdict == verdict, (page.name, law, p.verdict, p.note)
        if witness:
            assert witness_matches(witness, p.counterexample or ""), (witness, p.counterexample)
