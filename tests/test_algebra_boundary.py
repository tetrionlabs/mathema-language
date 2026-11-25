# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The term algebra sits behind one module, `text/_algebra.py`: every
name `text/_regular.py` held before the split still imports from it, the
algebra's names are the algebra module's own objects, and no other
module of the package reaches an algebra name through `_regular`."""
import ast
import importlib
from pathlib import Path

import pytest

from mathema_language.text import _regular

SRC = Path(__file__).parent.parent / "src" / "mathema_language"

#: every module-level name of text/_regular.py before the split
BEFORE = ["Context", "DIALECTS", "Expr", "FLAG_WORDS", "Node", "NotRegular", "OtherVersion", "PREDICATES", "Piece", "RUNNING", "Ranges", "TERM_VERSION", "_ADMITTED", "_ANY_PLUS", "_ANY_STAR", "_AT_EDGE", "_B_IN_EMPTY", "_CATEGORY_CLASS", "_DERIVATIVES", "_EMPTY_RE", "_EPS", "_EVERY_CODE_POINT", "_EVERY_STRING", "_FULL", "_ITEM_CHARS", "_LOWERS_INTO", "_MAX_CODE", "_METHODS", "_NONE", "_READ", "_Regex", "_TERMS", "_TRIVIAL", "_UNROLL", "_VERSIONS", "_WRITTEN", "_alt", "_boundary", "_cat", "_chars_re", "_class_chars", "_code", "_cs_complement", "_cs_has", "_cs_inter", "_cs_union", "_ctx_and", "_ctx_possible", "_ctx_text", "_derivative", "_edge", "_ends_in", "_every_code_point", "_inter", "_item_chars", "_join", "_loop", "_lowers_into", "_meaning", "_merge", "_nonempty", "_nullable", "_power", "_ranges", "_re_sets", "_singles", "_sre", "_text", "_to_node", "_written", "admits", "admits_after_json", "canonical", "canonical_is_stable", "canonical_text", "class_bounds", "code_points", "code_units", "every_string_over", "every_string_over_class", "exact", "from_node", "holds", "member", "of_length", "regex_language", "runs", "shortest", "term", "term_hash", "to_node", "version_dependent_characters", "versions_data"]

#: the names that are the algebra's
ALGEBRA = ["TERM_VERSION", "Ranges", "Expr", "Node", "_MAX_CODE", "_FULL", "_NONE", "_cs_union", "_cs_complement", "_cs_inter", "_cs_has", "_EPS", "_EMPTY_RE", "_ANY_STAR", "_ANY_PLUS", "_chars_re", "_cat", "_alt", "_inter", "_loop", "_nullable", "_re_sets", "to_node", "_to_node", "from_node", "_EVERY_STRING", "_code", "_ranges", "_text", "canonical", "_meaning", "term_hash", "canonical_text", "_DERIVATIVES", "_derivative", "holds", "member", "_READ", "code_units", "code_points", "shortest", "every_string_over", "of_length"]


def _algebra():
    return importlib.import_module("mathema_language.text._algebra")


@pytest.mark.parametrize("name", BEFORE)
def test_every_name_still_imports_from_where_it_did(name):
    assert hasattr(_regular, name)


@pytest.mark.parametrize("name", ALGEBRA)
def test_an_algebra_name_is_the_algebra_module_s_own_object(name):
    own = getattr(_algebra(), name)
    assert getattr(_regular, name) is own
    if callable(own) and hasattr(own, "__module__") and not name[0].isupper():
        assert own.__module__ == "mathema_language.text._algebra"


def test_the_compiler_s_names_are_not_in_the_algebra_module():
    algebra = _algebra()
    for name in sorted(set(BEFORE) - set(ALGEBRA)):
        assert not hasattr(algebra, name), name


def test_the_algebra_module_imports_nothing_of_the_package():
    tree = ast.parse((SRC / "text" / "_algebra.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0 and not (node.module or "").startswith("mathema"), ast.unparse(node)
        elif isinstance(node, ast.Import):
            assert not any(a.name.startswith("mathema") for a in node.names), ast.unparse(node)


def _reaches_through_regular(path):
    """The algebra names a module takes from `_regular`: imported from it by name, or read as
    an attribute of a name bound to it."""
    tree = ast.parse(path.read_text())
    found, bound = [], set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[-1] == "_regular":
            found += [a.name for a in node.names if a.name in ALGEBRA]
        elif isinstance(node, ast.ImportFrom):
            bound |= {a.asname or a.name for a in node.names if a.name == "_regular"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                and node.value.id in bound and node.attr in ALGEBRA:
            found.append(node.attr)
    return sorted(set(found))


def test_no_other_module_reaches_the_algebra_through_the_compiler():
    reached = {str(path.relative_to(SRC)): names for path in sorted(SRC.rglob("*.py"))
               if path.name not in ("_regular.py", "_algebra.py")
               and (names := _reaches_through_regular(path))}
    assert reached == {}
