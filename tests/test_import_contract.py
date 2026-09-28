# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The import contract with mathema, pinned: the only module that
names mathema is `_surface.py`, the only path it imports from is
`mathema.interfaces.extension`, every name it takes is on that
surface, and no source module imports an optional ecosystem at module
level. A rename inside mathema then fails here, under the surface's own
version policy, and never as a traceback somewhere else."""
import ast
import pathlib

import pytest

SRC = pathlib.Path(__file__).resolve().parent.parent / "src" / "mathema_language"
ECOSYSTEMS = {"pydantic", "jsonschema", "sqlalchemy", "django", "pandas",
              "pandera", "polars", "pyarrow", "duckdb", "pyspark"}


def _modules():
    return sorted(SRC.rglob("*.py"))


def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node, alias.name, None
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            for alias in node.names:
                yield node, node.module or "", alias.name


def _module_level(tree):
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            yield node


def test_only_the_surface_module_names_mathema():
    offenders = []
    for path in _modules():
        for _, module, _ in _imports(path):
            names_mathema = module == "mathema" or module.startswith("mathema.")
            if names_mathema and (path.name != "_surface.py"
                                  or module != "mathema.interfaces.extension"):
                offenders.append(f"{path.relative_to(SRC)}: {module}")
    assert offenders == []


def test_every_surface_name_is_on_the_surface():
    extension = pytest.importorskip("mathema.interfaces.extension")
    on_surface = {name for names in extension.SURFACE.values() for name in names}
    on_surface.add("EXTENSION_API_VERSION")
    taken = {name for _, module, name in _imports(SRC / "_surface.py")
             if module == "mathema.interfaces.extension"}
    assert taken <= on_surface, sorted(taken - on_surface)


def test_no_ecosystem_is_imported_at_module_level():
    # the lexicon's schema models are the one place an ecosystem is
    # imported at the top, and they load only when a claim names them;
    # the test below holds the lexicon to that
    offenders = []
    for path in _modules():
        if "_lexicon_models" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in _module_level(tree):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module or ""])
            for name in names:
                if name.split(".")[0] in ECOSYSTEMS:
                    offenders.append(f"{path.relative_to(SRC)}: {name}")
    assert offenders == []


def test_every_source_file_carries_the_licence_header():
    bad = []
    for path in [*_modules(), *sorted((SRC.parent.parent / "tests").glob("*.py"))]:
        lines = path.read_text(encoding="utf-8").splitlines()[:2]
        if lines != ["# SPDX-License-Identifier: Apache-2.0",
                     "# Copyright 2026 Tetrion Ltd"]:
            bad.append(str(path))
    assert bad == []


def test_the_lexicon_imports_no_ecosystem():
    import subprocess
    import sys
    code = ("import sys, mathema_language.lexicon; "
            f"print(sorted(m for m in sys.modules if m.split('.')[0] in {ECOSYSTEMS!r}))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]", out.stdout
