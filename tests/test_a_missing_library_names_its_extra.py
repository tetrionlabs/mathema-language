"""A language or adaptor that needs an optional library which is not installed
raises MissingLibrary, naming the library and the extra to install."""
import importlib
import importlib.util
import sys

import pytest

from mathema_language._missing import MissingLibrary


def _assert_names(e: MissingLibrary, library: str, extra: str) -> None:
    assert isinstance(e, ImportError)
    assert e.missing_library == library
    assert e.extra == extra
    assert e.distribution == "mathema-language"
    assert str(e).endswith(f"install mathema-language[{extra}]")


def _fresh_import(monkeypatch, module: str, absent: list[str]):
    for name in absent:
        monkeypatch.setitem(sys.modules, name, None)
    monkeypatch.delitem(sys.modules, module, raising=False)
    return importlib.import_module(module)


def test_the_error_carries_its_attributes_and_message():
    e = MissingLibrary("L[x]", "lib.sub", "ex")
    assert str(e) == "L[x] is read with lib.sub, which is not installed; install mathema-language[ex]"
    _assert_names(e, "lib.sub", "ex")


def test_yaml_without_ruamel(monkeypatch):
    with pytest.raises(MissingLibrary) as raised:
        _fresh_import(monkeypatch, "mathema_language.text.yaml_language",
                      ["ruamel.yaml", "ruamel"])
    _assert_names(raised.value, "ruamel.yaml", "yaml")


def test_toml_without_tomli_before_python_311(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 10, 0, "final", 0))
    with pytest.raises(MissingLibrary) as raised:
        _fresh_import(monkeypatch, "mathema_language.text.toml_language", ["tomli"])
    _assert_names(raised.value, "tomli", "toml")


def test_schema_inclusion_without_z3(monkeypatch):
    from mathema_language import smt
    monkeypatch.setitem(sys.modules, "z3", None)
    with pytest.raises(MissingLibrary) as raised:
        smt._z3()
    _assert_names(raised.value, "z3", "smt")
    assert "schema inclusion" in str(raised.value)


def test_a_json_schema_without_jsonschema(monkeypatch):
    from mathema_language.schema.adaptors.jsonschema import adapt
    monkeypatch.setattr(importlib.util, "find_spec",
                        lambda name, *a: None if name == "jsonschema" else object())
    schema = {"type": "object", "properties": {"a": {"type": "string"}}}
    with pytest.raises(MissingLibrary) as raised:
        adapt(schema)
    _assert_names(raised.value, "jsonschema", "jsonschema")
