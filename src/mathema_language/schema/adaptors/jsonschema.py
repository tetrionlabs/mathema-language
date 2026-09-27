# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A JSON Schema (a dict with `type: object` and `properties`) as a
row schema: property types, `required`, `additionalProperties`,
bounds, lengths, `pattern`, `enum` and `const` read into the neutral
model; members are dicts validated by `jsonschema`. A `$ref` is
refused at adaptation."""
from __future__ import annotations

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


def _type_of(prop: dict[str, Any]) -> tuple[NeutralType, bool]:
    """`(type, nullable)` of one property."""
    if "$ref" in prop:
        raise ValueError("a $ref in a JSON Schema is not read; inline the definition")
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
    """The row schema of a JSON Schema object."""
    policy = "exact" if schema.get("additionalProperties") is False else "open"
    return RowSchema(str(schema.get("title") or "object"), tuple(_fields(schema)), column_policy=policy)


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
