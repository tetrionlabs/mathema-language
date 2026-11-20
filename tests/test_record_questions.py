# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""An acceptance sheet: twenty-three inclusion questions between record
languages written as JSON Schema, shaped like sets of permissions
(tools, paths, hosts, commands, a lifetime), each with the verdict
wanted. A question the record inclusion decides asserts its verdict, and
a falsified one its witness against both validators; one it does not
decide yet is a strict expected failure, so it reports the day it is
decided."""
import pytest

pytest.importorskip("z3")
pytest.importorskip("jsonschema")

from mathema_language import smt  # noqa: E402
from mathema_language.schema.adaptors import adapt_row  # noqa: E402


def obj(props, required=None, closed=True):
    out = {"type": "object", "properties": props,
           "required": list(props) if required is None else required}
    if closed:
        out["additionalProperties"] = False
    return out


def text(**keywords):
    return {"type": "string", **keywords}


def items(of, **keywords):
    return {"type": "array", "items": of, **keywords}


def one_of(*values):
    return {"enum": list(values)}


BOOLEAN = {"type": "boolean"}
DEEP, SHALLOW = r"^/wt/task-7(/[a-z0-9_.-]+)*", r"^/wt(/[a-z0-9_.-]+)*"

#: name: (older, newer, the verdict wanted, whether it is decided today)
QUESTIONS = {
    "1 a list of tools inside a wider list": (
        obj({"tools": items(one_of("read", "grep"))}),
        obj({"tools": items(one_of("read", "grep", "edit"))}), "proven", True),
    "1b the wider list inside the narrower": (
        obj({"tools": items(one_of("read", "grep", "edit"))}),
        obj({"tools": items(one_of("read", "grep"))}), "falsified", True),
    "2 a set of tools, no tool twice": (
        obj({"tools": items(one_of("read", "grep"), uniqueItems=True)}),
        obj({"tools": items(one_of("read", "grep", "edit"), uniqueItems=True)}), "proven", False),
    "3 a flag held false inside a boolean": (
        obj({"edit": BOOLEAN, "merge": {"const": False}}),
        obj({"edit": BOOLEAN, "merge": BOOLEAN}), "proven", False),
    "3b a boolean inside a flag held false": (
        obj({"merge": BOOLEAN}), obj({"merge": {"const": False}}), "falsified", False),
    "3c a flag from a list of one inside a boolean": (
        obj({"merge": one_of(False)}), obj({"merge": BOOLEAN}), "proven", True),
    "3d a boolean inside a flag from a list of one": (
        obj({"merge": BOOLEAN}), obj({"merge": one_of(False)}), "falsified", True),
    "4 a deeper path pattern inside a shallower, ending in a dollar": (
        obj({"root": text(pattern=DEEP + "$")}), obj({"root": text(pattern=SHALLOW + "$")}),
        "proven", True),
    "4b the shallower inside the deeper": (
        obj({"root": text(pattern=SHALLOW + "$")}), obj({"root": text(pattern=DEEP + "$")}),
        "falsified", True),
    "4c the same ending at the end of text": (
        obj({"root": text(pattern=DEEP + r"\Z")}), obj({"root": text(pattern=SHALLOW + r"\Z")}),
        "proven", True),
    "5 a list of paths by the pattern of each": (
        obj({"write": items(text(pattern=r"^/wt/task-7/.*$"))}),
        obj({"write": items(text(pattern=r"^/wt/.*$"))}), "proven", True),
    "6 a list of hosts with a longest length": (
        obj({"hosts": items(one_of("github.com"), maxItems=3)}),
        obj({"hosts": items(one_of("github.com", "pypi.org"), maxItems=5)}), "proven", True),
    "7 a closed record inside a record": (
        obj({"shell": obj({"git": items(one_of("status", "diff"))})}),
        obj({"shell": obj({"git": items(one_of("status", "diff", "commit"))})}), "proven", False),
    "8 a list that must not hold a member": (
        obj({"tools": items(one_of("read", "grep"))}),
        obj({"tools": {**items(one_of("read", "grep", "merge")),
                       "not": {"contains": {"const": "merge"}}}}), "proven", False),
    "9 a lifetime in minutes": (
        obj({"minutes": {"type": "integer", "minimum": 1, "maximum": 60}}),
        obj({"minutes": {"type": "integer", "minimum": 1, "maximum": 480}}), "proven", True),
    "10 either of two templates": (
        {"anyOf": [obj({"role": {"const": "build"}, "tools": items(one_of("edit"))}),
                   obj({"role": {"const": "review"}, "tools": items(one_of("read"))})]},
        obj({"role": one_of("build", "review"), "tools": items(one_of("edit", "read"))}),
        "proven", False),
    "11 commands required when the shell is among the tools": (
        obj({"tools": items(one_of("shell", "read")), "commands": items(text())}),
        {**obj({"tools": items(one_of("shell", "read")), "commands": items(text())},
               required=["tools"]),
         "if": {"properties": {"tools": {"contains": {"const": "shell"}}}},
         "then": {"required": ["commands"]}}, "proven", False),
    "12 a list that must hold a member": (
        obj({"tools": {**items(one_of("read", "grep")), "contains": {"const": "read"}}}),
        obj({"tools": items(one_of("read", "grep"), minItems=1)}), "proven", False),
    "13 a map from any tool to a rule": (
        {"type": "object", "additionalProperties": one_of("allow")},
        {"type": "object", "additionalProperties": one_of("allow", "ask")}, "proven", False),
    "14 a map whose keys come from a list": (
        {"type": "object", "propertyNames": one_of("read", "grep"), "additionalProperties": BOOLEAN},
        {"type": "object", "propertyNames": one_of("read", "grep", "edit"),
         "additionalProperties": BOOLEAN}, "proven", False),
    "15 a list of hosts inside a pattern": (
        obj({"host": one_of("api.github.com", "github.com")}),
        obj({"host": text(pattern=r"^([a-z0-9-]+\.)*github\.com\Z")}), "proven", True),
    "16 a pattern of two words inside a list of three": (
        obj({"cmd": text(pattern=r"^(status|diff)\Z")}),
        obj({"cmd": one_of("status", "diff", "log")}), "proven", True),
    "17 a pattern with a longest length inside a pattern": (
        obj({"cmd": text(pattern=r"^git (status|diff)\Z", maxLength=20)}),
        obj({"cmd": text(pattern=r"^git [a-z]+\Z")}), "proven", True),
}


def _cases():
    for name, (older, newer, wanted, decided) in QUESTIONS.items():
        marks = [] if decided else [pytest.mark.xfail(strict=True, reason="not yet built")]
        yield pytest.param(older, newer, wanted, id=name, marks=marks)


def test_there_are_twenty_three_questions():
    assert len(QUESTIONS) == 23
    assert sum(decided for *_, decided in QUESTIONS.values()) == 13


@pytest.mark.parametrize("older, newer, wanted", list(_cases()))
def test_the_question_has_the_verdict_wanted(older, newer, wanted):
    try:
        result = smt._schema_inclusion(older, newer)
    except Exception as e:
        pytest.fail(f"raised {type(e).__name__}: {e}")
    assert result.verdict == wanted, result
    if wanted == "falsified":
        assert adapt_row(older).contains(result.witness)
        assert not adapt_row(newer).contains(result.witness)


@pytest.mark.parametrize("name", [n for n, q in QUESTIONS.items() if not q[3]])
def test_a_question_not_decided_is_never_answered_wrongly(name):
    older, newer, wanted, _ = QUESTIONS[name]
    try:
        result = smt._schema_inclusion(older, newer)
    except Exception:
        return
    assert result.verdict in ("unknown", wanted), result
