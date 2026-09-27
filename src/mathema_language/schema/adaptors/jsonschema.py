# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A JSON Schema (a dict with `type: object` and `properties`) as a
row schema: property types, `required`, `additionalProperties`,
bounds, lengths, `pattern`, `enum` and `const` read into the neutral
model; members are dicts validated by `jsonschema`. A `$ref` is
refused at adaptation."""
from __future__ import annotations

import contextvars
import importlib.util
from typing import Any

from ..._priority import DOCUMENT, priority
from ..ecosystems.jsonschema import JsonSchemaEcosystem
from ..languages import RowLanguage
from ..model import NO_DEFAULT, Constraints, Field, NeutralType, RowSchema

_BASES = {"boolean": "bool", "integer": "int", "number": "float", "string": "string",
          "array": "list", "object": "struct", "null": "any"}


def _looks_like_row_schema(obj: Any) -> bool:
    return isinstance(obj, dict) and obj.get("type") == "object" and isinstance(obj.get("properties"), dict)


_CONTEXT: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "the JSON Schema being read", default=None)


def _ref_type(ref: str) -> NeutralType:
    """A local `$ref` (`#`, `#/$defs/<name>`, `#/definitions/<name>`)
    as a `ref` to a named definition, read the first time it is met."""
    context = _CONTEXT.get()
    if context is None:
        raise ValueError(f"$ref {ref!r} outside a schema being read")
    if ref == "#":
        return NeutralType("ref", ref=context["name"])
    for prefix in ("#/$defs/", "#/definitions/"):
        if ref.startswith(prefix):
            name = ref[len(prefix):]
            if "/" in name:
                break
            if name not in context["definitions"] and name not in context["reading"]:
                target = (context["root"].get(prefix[2:-1]) or {}).get(name)
                if not isinstance(target, dict):
                    raise ValueError(f"$ref {ref!r} names no definition in the schema")
                context["reading"].add(name)
                fields = _fields(target) if isinstance(target.get("properties"), dict) else []
                context["reading"].discard(name)
                policy = "exact" if target.get("additionalProperties") is False else "open"
                context["definitions"][name] = RowSchema(name, tuple(fields), column_policy=policy)
            return NeutralType("ref", ref=name)
    raise ValueError(f"$ref {ref!r} is not read: only local references (#, #/$defs/..., "
                     "#/definitions/...) are; inline or bundle the rest")


def _type_of(prop: dict[str, Any]) -> tuple[NeutralType, bool]:
    """`(type, nullable)` of one property."""
    if "$ref" in prop:
        return _ref_type(str(prop["$ref"])), False
    if "enum" in prop and "type" not in prop:
        return NeutralType("categorical", levels=tuple(prop["enum"])), None in prop["enum"]
    if "anyOf" in prop or "oneOf" in prop:
        options = list(prop.get("anyOf") or prop.get("oneOf") or [])
        nullable = any(o.get("type") == "null" for o in options)
        others = [o for o in options if o.get("type") != "null"]
        if len(others) == 1:
            t, inner_nullable = _type_of(others[0])
            return t, nullable or inner_nullable
        return NeutralType("any"), nullable
    kind = prop.get("type")
    nullable = False
    if isinstance(kind, list):
        nullable = "null" in kind
        kinds = [k for k in kind if k != "null"]
        kind = kinds[0] if len(kinds) == 1 else None
    if kind is None:
        return NeutralType("any"), nullable
    base = _BASES.get(kind, "any")
    if base == "list":
        items = prop.get("items")
        item = _type_of(items)[0] if isinstance(items, dict) else None
        return NeutralType("list", item=item), nullable
    if base == "struct":
        if isinstance(prop.get("properties"), dict):
            return NeutralType("struct", fields=tuple(_fields(prop))), nullable
        return NeutralType("map", key=NeutralType("string"),
                           value=_type_of(prop["additionalProperties"])[0]
                           if isinstance(prop.get("additionalProperties"), dict) else None), nullable
    return NeutralType(base), nullable


def _constraints(prop: dict[str, Any]) -> Constraints:
    return Constraints(min=prop.get("minimum"), max=prop.get("maximum"),
                       exclusive_min=prop.get("exclusiveMinimum"),
                       exclusive_max=prop.get("exclusiveMaximum"),
                       min_len=prop.get("minLength", prop.get("minItems")),
                       max_len=prop.get("maxLength", prop.get("maxItems")),
                       regex=prop.get("pattern"),
                       enum=tuple(prop["enum"]) if "enum" in prop and "type" in prop else None,
                       const=prop.get("const", NO_DEFAULT), multiple_of=prop.get("multipleOf"))


def _fields(schema: dict[str, Any]) -> list[Field]:
    required = set(schema.get("required", ()))
    out: list[Field] = []
    for name, prop in schema["properties"].items():
        if not isinstance(prop, dict):
            prop = {}
        t, nullable = _type_of(prop)
        out.append(Field(name, t, nullable=nullable, required=name in required,
                         constraints=_constraints(prop),
                         default=prop.get("default", NO_DEFAULT)))
    return out


def schema_of(schema: dict[str, Any]) -> RowSchema:
    """The row schema of a JSON Schema object, its local `$ref`s read
    into named definitions."""
    name = str(schema.get("title") or "object")
    context: dict[str, Any] = {"root": schema, "name": name, "definitions": {},
                               "reading": set()}
    token = _CONTEXT.set(context)
    try:
        fields = _fields(schema)
    finally:
        _CONTEXT.reset(token)
    policy = "exact" if schema.get("additionalProperties") is False else "open"
    return RowSchema(name, tuple(fields), column_policy=policy,
                     definitions=tuple(context["definitions"].items()))


@priority(DOCUMENT)
def adapt(obj: Any) -> RowLanguage | None:
    """The row language of a JSON Schema object, or None for anything
    else; a JSON Schema with the jsonschema package not installed is
    refused with the extra to install."""
    if not _looks_like_row_schema(obj):
        return None
    if importlib.util.find_spec("jsonschema") is None:
        raise ImportError("a JSON Schema is validated by the jsonschema package, which is not "
                          "installed: pip install 'mathema-language[jsonschema]'")
    return RowLanguage(schema_of(obj), JsonSchemaEcosystem(obj))


__all__ = ["adapt", "schema_of"]
