# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Checks shared by the README and the reference pages, whose examples
are the shop in `examples/shop`: code a page shows is the shop's own,
docstrings aside, and a claim a page states lands on the verdict it
states."""
import ast
import importlib
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
_BLOCK = re.compile(r"(<!-- output -->\n)?```(python|text)\n(.*?)```", re.S)
_VERDICT = re.compile(r"^\s+(proven|holds|falsified|unknown|skipped)(?:\s{2,}(.*))?$")
_ROW = re.compile(r"^\| `([^`]+)` \| `(.+?)` \| (\w+) \|", re.M)


def shop_module(name):
    """`shop.<name>`, importable from `examples/`."""
    if str(EXAMPLES) not in sys.path:
        sys.path.insert(0, str(EXAMPLES))
    return importlib.import_module(f"shop.{name}")


def _stripped(node):
    for n in ast.walk(node):
        body = getattr(n, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) \
                and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            n.body = body[1:] or [ast.Pass()]
    return ast.dump(node)


def _named(tree):
    """Each top-level definition or assignment in a module, by name."""
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            out[node.name] = node
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            out[node.targets[0].id] = node
    return out


def blocks(text):
    """`(kind, body, is_output)` for every fenced python or text block."""
    return [(kind, body, bool(marker)) for marker, kind, body in _BLOCK.findall(text)]


def is_shown_code(body):
    """Whether a python block shows shop code (it defines something)."""
    return any(isinstance(n, (ast.FunctionDef, ast.ClassDef)) for n in ast.parse(body).body)


def definition_problems(text, modules):
    """Every definition a page shows that is not the shop's own."""
    found = {}
    for module in modules:
        found.update(_named(ast.parse(pathlib.Path(module.__file__).read_text())))
    problems = []
    for kind, body, _ in blocks(text):
        if kind != "python" or not is_shown_code(body):
            continue
        for name, node in _named(ast.parse(body)).items():
            if name not in found:
                problems.append(f"{name} is not in the shop")
            elif _stripped(node) != _stripped(found[name]):
                problems.append(f"{name} differs from the shop's")
    return problems


def claim_blocks(text):
    """`(function, claim, verdict, witness)` for every claim a text block
    states after an `f = name` line."""
    out, fn = [], None
    for kind, body, is_output in blocks(text):
        if kind != "text" or is_output:
            continue
        lines = body.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("f = "):
                fn = line[4:].strip()
            elif line.startswith("for ") and i + 1 < len(lines) and _VERDICT.match(lines[i + 1]):
                m = _VERDICT.match(lines[i + 1])
                out.append((fn, line, m.group(1), m.group(2)))
    return out


def claim_rows(text):
    """`(function, claim, verdict)` for every claim row of a table."""
    return _ROW.findall(text)
