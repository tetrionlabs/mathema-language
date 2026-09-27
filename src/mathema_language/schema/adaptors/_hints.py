# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Type hints read into the neutral model, shared by the
standard-library adaptors: the scalar types, `Optional`, `Literal`,
`Annotated` with duck-typed constraint markers (anything with `gt`,
`ge`, `lt`, `le`, `min_length`, `max_length`, `multiple_of` or
`pattern`), lists, dicts and nested records."""
from __future__ import annotations

import contextvars
import dataclasses
import datetime as _dt
import decimal
import types
import typing
from typing import Any

from ..model import Constraints, Field, NeutralType, RowSchema

_SCALARS: dict[Any, str] = {
    bool: "bool", int: "int", float: "float", decimal.Decimal: "decimal",
    str: "string", bytes: "binary", bytearray: "binary", _dt.date: "date",
    _dt.time: "time", _dt.datetime: "datetime", _dt.timedelta: "duration",
}

_MARKERS = (("gt", "exclusive_min"), ("ge", "min"), ("lt", "exclusive_max"),
            ("le", "max"), ("min_length", "min_len"), ("max_length", "max_len"),
            ("multiple_of", "multiple_of"), ("pattern", "regex"))


def constraints_of(markers: tuple[Any, ...]) -> Constraints:
    """The constraints the `Annotated` markers spell, read by
    attribute so `annotated_types`, pydantic's `Field` and any
    look-alike all work."""
    found: dict[str, Any] = {}
    for marker in markers:
        for attr, key in _MARKERS:
            value = getattr(marker, attr, None)
            if value is not None:
                found[key] = value
        if isinstance(marker, (list, tuple, set, frozenset)) and marker:
            found["enum"] = tuple(marker)
    return Constraints(**found)


def field_of(name: str, hint: Any, *, required: bool = True, default: Any = ...,
             extra_markers: tuple[Any, ...] = ()) -> Field:
    """One field from a type hint: `Optional` makes it nullable,
    `Annotated` markers become constraints, a default is kept."""
    from ..model import NO_DEFAULT
    markers: tuple[Any, ...] = extra_markers
    nullable = False
    while True:
        origin = typing.get_origin(hint)
        if origin is typing.Annotated:
            args = typing.get_args(hint)
            hint, markers = args[0], markers + tuple(args[1:])
            continue
        if origin in (typing.Union, types.UnionType):
            members = [a for a in typing.get_args(hint) if a is not type(None)]
            if len(members) < len(typing.get_args(hint)):
                nullable = True
            hint = members[0] if len(members) == 1 else members
            if isinstance(hint, list):
                hint = Any
            continue
        break
    t = type_of(hint)
    return Field(name, t, nullable=nullable, required=required,
                 constraints=constraints_of(markers),
                 default=NO_DEFAULT if default is ... else default)


_READING: contextvars.ContextVar[dict[Any, str] | None] = contextvars.ContextVar(
    "record types being read", default=None)
_DEFINITIONS: contextvars.ContextVar[dict[str, RowSchema] | None] = contextvars.ContextVar(
    "record types read", default=None)


def record_name(cls: Any) -> str:
    """The name a record type goes by in a schema's definitions."""
    return str(getattr(cls, "__qualname__", None) or getattr(cls, "__name__", repr(cls)))


def _construct_of(cls: Any) -> Any:
    """How a struct of this record type is built from its field values."""
    if isinstance(cls, type) and dataclasses.is_dataclass(cls):
        return cls
    if isinstance(cls, type) and isinstance(getattr(cls, "model_fields", None), dict):
        return getattr(cls, "model_construct", None)
    return None


def _record_fields(cls: Any) -> list[Field] | None:
    if isinstance(cls, type) and dataclasses.is_dataclass(cls):
        return dataclass_fields(cls)
    if typing.is_typeddict(cls):
        return typeddict_fields(cls)
    if isinstance(cls, type) and isinstance(getattr(cls, "model_fields", None), dict):
        return pydantic_fields(cls)
    return None


def read_record(cls: Any) -> tuple[list[Field], tuple[tuple[str, RowSchema], ...]]:
    """The fields of a record type and every record type reached from
    it, as definitions: a type met again while it is still being read
    is a `ref` to it, which is how a schema that refers to itself is
    read without reading forever."""
    reading = _READING.get()
    definitions = _DEFINITIONS.get()
    outermost = reading is None
    if outermost:
        reading, definitions = {}, {}
        tokens = (_READING.set(reading), _DEFINITIONS.set(definitions))
    assert reading is not None and definitions is not None
    try:
        reading[cls] = record_name(cls)
        fields = _record_fields(cls) or []
        del reading[cls]
        definitions[record_name(cls)] = RowSchema(
            record_name(cls), tuple(fields), construct=_construct_of(cls))
        return fields, tuple(definitions.items())
    finally:
        if outermost:
            _READING.reset(tokens[0])
            _DEFINITIONS.reset(tokens[1])


def _record_type(hint: Any) -> NeutralType:
    reading = _READING.get()
    if reading is not None and hint in reading:
        return NeutralType("ref", ref=reading[hint], construct=_construct_of(hint))
    fields, _ = read_record(hint)
    return NeutralType("struct", fields=tuple(fields), construct=_construct_of(hint))


def type_of(hint: Any) -> NeutralType:
    """The neutral type a hint names, `any` when it names none."""
    if hint in _SCALARS:
        return NeutralType(_SCALARS[hint])
    origin = typing.get_origin(hint)
    if origin is typing.Literal:
        return NeutralType("categorical", levels=tuple(typing.get_args(hint)))
    if origin in (list, tuple, set, frozenset, typing.Sequence):
        args = typing.get_args(hint)
        item = type_of(args[0]) if args and args[0] is not Ellipsis else None
        return NeutralType("list", item=item)
    if origin in (dict, typing.Mapping):
        args = typing.get_args(hint)
        return NeutralType("map", key=type_of(args[0]) if args else None,
                           value=type_of(args[1]) if len(args) > 1 else None)
    if (isinstance(hint, type) and dataclasses.is_dataclass(hint)) or typing.is_typeddict(hint) \
            or (isinstance(hint, type) and isinstance(getattr(hint, "model_fields", None), dict)):
        return _record_type(hint)
    if isinstance(hint, type) and issubclass(hint, bool):
        return NeutralType("bool")
    if isinstance(hint, type):
        for scalar, base in _SCALARS.items():
            if issubclass(hint, scalar):
                return NeutralType(base)
    return NeutralType("any")


def dataclass_fields(cls: type) -> list[Field]:
    """The fields of a dataclass, defaults kept."""
    hints = typing.get_type_hints(cls, include_extras=True)
    out: list[Field] = []
    for f in dataclasses.fields(cls):
        default: Any = ...
        if f.default is not dataclasses.MISSING:
            default = f.default
        elif f.default_factory is not dataclasses.MISSING:
            default = f.default_factory()
        out.append(field_of(f.name, hints.get(f.name, Any), default=default))
    return out


def typeddict_fields(cls: Any) -> list[Field]:
    """The keys of a TypedDict, optional keys not required."""
    hints = typing.get_type_hints(cls, include_extras=True)
    required = getattr(cls, "__required_keys__", frozenset(hints))
    return [field_of(name, hint, required=name in required) for name, hint in hints.items()]


def pydantic_fields(cls: Any) -> list[Field]:
    """The fields of a pydantic model, read off `model_fields` by
    attribute (annotation, required, default, metadata markers) so
    this module never imports pydantic."""
    out: list[Field] = []
    for name, info in cls.model_fields.items():
        required = bool(info.is_required())
        default: Any = ... if required else info.default
        if getattr(info, "default_factory", None) is not None:
            default = ...
        out.append(field_of(name, info.annotation, required=required, default=default,
                            extra_markers=tuple(getattr(info, "metadata", ()) or ())))
    return out


__all__ = ["constraints_of", "dataclass_fields", "field_of", "pydantic_fields", "type_of",
           "typeddict_fields"]
