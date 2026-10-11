# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""An `argparse.ArgumentParser` as the language of the namespaces its
`parse_args` returns. Each action is a field of the namespace: its
`dest`, its type, `nargs`, `choices`, default and constants read as
argparse applies them. A parser with subcommands is a union, one
branch per subcommand, each with the parser's own fields, the
subcommand's fields and its `set_defaults`. A zero-argument function
annotated to return an `ArgumentParser` is called to build one, which
is how a command line is usually written. Members are
`argparse.Namespace` objects, checked by the neutral checker."""
from __future__ import annotations

import argparse
import inspect
from typing import Any

from ...adaptor_priority import LIBRARY, priority
from ..ecosystems.namespace import NamespaceEcosystem
from ..languages import RowLanguage
from ..model import NO_DEFAULT, Constraints, Field, NeutralType, RowSchema
from ..union import UnionLanguage

#: the argument types read as neutral types; any other callable is kept
#: as a converter, and the field is drawn as text and converted
_TYPES = {None: "string", str: "string", int: "int", float: "float"}

_SKIPPED = (argparse._HelpAction, argparse._VersionAction)


def _builds_a_parser(obj: Any) -> bool:
    """A function of no arguments whose return annotation names
    `ArgumentParser`."""
    if not inspect.isfunction(obj):
        return False
    try:
        signature = inspect.signature(obj)
    except (TypeError, ValueError):
        return False
    if any(p.default is inspect.Parameter.empty and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
           for p in signature.parameters.values()):
        return False
    annotation = signature.return_annotation
    return annotation is argparse.ArgumentParser or \
        (isinstance(annotation, str) and annotation.split(".")[-1] == "ArgumentParser")


def _scalar(action: argparse.Action, converters: dict[str, Any]) -> NeutralType:
    """The type one value of the action has once argparse has applied
    `type` to it."""
    if action.choices is not None and not isinstance(action, argparse._SubParsersAction):
        return NeutralType("categorical", levels=tuple(action.choices))
    convert = action.type
    if convert in _TYPES:
        return NeutralType(_TYPES[convert])
    if convert is bool:
        return NeutralType("bool")
    if callable(convert):
        converters[action.dest] = convert
    return NeutralType("string")


def _default(action: argparse.Action) -> Any:
    """The default as the namespace holds it: argparse applies `type` to
    a default given as text."""
    default = action.default
    if isinstance(default, str) and callable(action.type) and action.type is not str:
        try:
            return action.type(default)
        except Exception:
            return default
    return default


def _field(action: argparse.Action, converters: dict[str, Any]) -> Field | None:
    """The namespace field one action writes, or None for help and
    version, which end the program instead."""
    if isinstance(action, (*_SKIPPED, argparse._SubParsersAction)):
        return None
    dest = action.dest
    default = _default(action)
    suppressed = default is argparse.SUPPRESS
    nullable = default is None
    if isinstance(action, (argparse._StoreTrueAction, argparse._StoreFalseAction)):
        return Field(dest, NeutralType("bool"), nullable=False, required=not suppressed)
    if isinstance(action, argparse.BooleanOptionalAction):
        return Field(dest, NeutralType("bool"), nullable=nullable, required=not suppressed)
    if isinstance(action, argparse._StoreConstAction):
        levels = (action.const,) if default is None else (action.const, default)
        return Field(dest, NeutralType("categorical", levels=levels), nullable=nullable,
                     required=not suppressed)
    if isinstance(action, argparse._CountAction):
        return Field(dest, NeutralType("int"), nullable=nullable, required=not suppressed,
                     constraints=Constraints(min=0 if default is None else min(0, default)))
    if isinstance(action, argparse._AppendConstAction):
        item = NeutralType("categorical", levels=(action.const,))
        return Field(dest, NeutralType("list", item=item), nullable=nullable,
                     required=not suppressed)
    item = _scalar(action, converters)
    nargs = action.nargs
    many = isinstance(action, (argparse._AppendAction, argparse._ExtendAction)) \
        or nargs in ("*", "+", argparse.REMAINDER) or isinstance(nargs, int)
    if many:
        lengths = Constraints(min_len=1 if nargs == "+" else nargs if isinstance(nargs, int) else None,
                              max_len=nargs if isinstance(nargs, int) else None)
        return Field(dest, NeutralType("list", item=item), nullable=nullable or nargs == "*",
                     required=not suppressed, constraints=lengths)
    optional_value = nargs == "?" or (action.option_strings and not action.required)
    return Field(dest, item, nullable=bool(optional_value and nullable),
                 required=not suppressed, nan_allowed=action.type is float,
                 default=NO_DEFAULT if suppressed else default)


def _set_defaults(parser: argparse.ArgumentParser, taken: set[str]) -> list[Field]:
    """`set_defaults` entries no action writes, each a constant field
    (`func=handler` is the usual one)."""
    out: list[Field] = []
    for name, value in parser._defaults.items():
        if name in taken:
            continue
        out.append(Field(name, NeutralType("any"), constraints=Constraints(const=value)))
    return out


def _own_fields(parser: argparse.ArgumentParser, converters: dict[str, Any]) -> list[Field]:
    fields: dict[str, Field] = {}
    for action in parser._actions:
        f = _field(action, converters)
        if f is not None and f.name not in fields:
            fields[f.name] = f
    return list(fields.values()) + _set_defaults(parser, set(fields))


def _subparsers(parser: argparse.ArgumentParser) -> argparse._SubParsersAction[argparse.ArgumentParser] | None:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _shapes(parser: argparse.ArgumentParser, inherited: list[Field],
            converters: dict[str, Any], path: str) -> list[tuple[str, list[Field]]]:
    """`(name, fields)` for every namespace shape the parser can return:
    one per subcommand, recursively, or the parser's own fields when it
    has none."""
    own = inherited + _own_fields(parser, converters)
    sub = _subparsers(parser)
    if sub is None:
        return [(path, own)]
    names: dict[int, list[str]] = {}
    parsers: dict[int, argparse.ArgumentParser] = {}
    for name, child in sub.choices.items():
        names.setdefault(id(child), []).append(name)
        parsers[id(child)] = child
    out: list[tuple[str, list[Field]]] = []
    if not sub.required:
        none = [] if sub.dest is argparse.SUPPRESS else \
            [Field(sub.dest, NeutralType("categorical", levels=(None,)), nullable=True)]
        out.append((path, own + none))
    for key, child in parsers.items():
        chosen = [] if sub.dest is argparse.SUPPRESS else \
            [Field(sub.dest, NeutralType("categorical", levels=tuple(names[key])))]
        label = f"{path} {names[key][0]}".strip()
        out.extend(_shapes(child, own + chosen, converters, label))
    return out


def _language(parser: argparse.ArgumentParser) -> RowLanguage | UnionLanguage:
    converters: dict[str, Any] = {}
    shapes = _shapes(parser, [], converters, parser.prog)
    ecosystem = NamespaceEcosystem(converters)
    branches = []
    for name, fields in shapes:
        unique: dict[str, Field] = {}
        for f in fields:
            unique[f.name] = f
        branches.append(RowLanguage(RowSchema(name or "namespace", tuple(unique.values()),
                                              column_policy="exact"), ecosystem, name))
    if len(branches) == 1:
        return branches[0]

    def pick(value: Any) -> int | None:
        for i, branch in enumerate(branches):
            if branch.contains(value):
                return i
        return None

    return UnionLanguage(parser.prog, tuple(branches), pick)


def schema_shapes(parser: argparse.ArgumentParser) -> list[RowSchema]:
    """The row schema of every namespace shape the parser can return."""
    language = _language(parser)
    if isinstance(language, UnionLanguage):
        return [branch.schema for branch in language.branches]
    return [language.schema]


@priority(LIBRARY)
def adapt(obj: Any) -> RowLanguage | UnionLanguage | None:
    """The language of the namespaces a parser returns, or None for
    anything that is not a parser or a function building one."""
    if _builds_a_parser(obj):
        obj = obj()
    if not isinstance(obj, argparse.ArgumentParser):
        return None
    return _language(obj)


__all__ = ["adapt", "schema_shapes"]
