# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""An OpenAPI 3 operation as the language of the requests it accepts.

A request is a record: `{"path": {...}, "query": {...}, "headers": {...},
"cookies": {...}, "body": ...}`, one entry per place the operation takes
parameters, each holding the parameters as their schemas type them (a
query parameter declared as an integer is an int, not the text it
arrives as). `request_schema(spec, operation_id)` writes that record as
one JSON Schema, and `operation(spec, operation_id)` is its record
language, so a request is drawn, checked by `jsonschema` and encoded for
z3 like any JSON Schema record: "version 2 of the API accepts every
request version 1 did" is an inclusion between two such languages.

A path parameter is always required; a query, header or cookie parameter
when it says so; the body when `requestBody.required` is true. Local
references (`#/components/...`) are resolved by inlining them, and a
schema that refers to itself is refused by name. OpenAPI 3.0's
`nullable: true` reads as a type that also admits null. How a value is
spelt on the wire (`style`, `explode`, percent-encoding) is not read:
the language is of requests once their parameters are parsed.

`Operation` carries what the HTTP method says about an operation, as
the method's own semantics define it: a GET or HEAD reads only, a PUT
or DELETE is idempotent, and a DELETE destroys."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
_PLACES = {"path": "path", "query": "query", "header": "headers", "cookie": "cookies"}


@dataclass(frozen=True)
class Operation:
    """One operation of a specification: its `operation_id`, HTTP
    `method` and `path`, what its method says about it, and `language`,
    the requests it accepts."""
    operation_id: str
    method: str
    path: str
    language: Any

    @property
    def read_only(self) -> bool:
        return self.method in ("get", "head", "options", "trace")

    @property
    def idempotent(self) -> bool:
        return self.read_only or self.method in ("put", "delete")

    @property
    def destructive(self) -> bool:
        return self.method == "delete"


def _resolve(spec: dict[str, Any], node: Any, seen: tuple[str, ...] = ()) -> Any:
    """Intent:
        `node` with every local `$ref` inlined, and OpenAPI 3.0's `nullable: true` read as a type
        that also admits null.

    Raises:
        ValueError: a reference is not local, refers to itself, or names nothing in the
        specification.
    """
    if isinstance(node, list):
        return [_resolve(spec, item, seen) for item in node]
    if not isinstance(node, dict):
        return node
    ref = node.get("$ref")
    if isinstance(ref, str):
        if not ref.startswith("#/"):
            raise ValueError(f"$ref {ref!r} is not read: only references inside the specification")
        if ref in seen:
            raise ValueError(f"$ref {ref!r} refers to itself, which is not read")
        target: Any = spec
        for part in ref[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            if not isinstance(target, dict) or part not in target:
                raise ValueError(f"$ref {ref!r} names nothing in the specification")
            target = target[part]
        return _resolve(spec, target, (*seen, ref))
    out = {key: _resolve(spec, value, seen) for key, value in node.items()}
    if out.pop("nullable", False) is True and "type" in out:
        kind = out["type"]
        out["type"] = [*kind, "null"] if isinstance(kind, list) else [kind, "null"]
    return out


def _find(spec: dict[str, Any], operation_id: str) -> tuple[str, str, dict[str, Any], dict[str, Any]]:
    """Intent:
        `(path, method, path item, operation)` for the operation with this id.

    Raises:
        KeyError: no operation in the specification has that id.
    """
    for path, item in (spec.get("paths") or {}).items():
        for method in _METHODS:
            op = (item or {}).get(method)
            if isinstance(op, dict) and op.get("operationId") == operation_id:
                return path, method, item, op
    raise KeyError(f"no operation {operation_id!r} in the specification")


def operation_ids(spec: dict[str, Any]) -> list[str]:
    """Every operation id the specification declares, in its order."""
    return [op["operationId"] for item in (spec.get("paths") or {}).values()
            for method in _METHODS
            if isinstance((op := (item or {}).get(method)), dict) and "operationId" in op]


def request_schema(spec: dict[str, Any], operation_id: str) -> dict[str, Any]:
    """The JSON Schema of the requests one operation accepts."""
    path, method, item, op = _find(spec, operation_id)
    params: dict[tuple[str, str], dict[str, Any]] = {}
    for param in [*(item.get("parameters") or []), *(op.get("parameters") or [])]:
        param = _resolve(spec, param)
        params[(param["name"], param["in"])] = param
    places: dict[str, dict[str, Any]] = {}
    for (name, where), param in params.items():
        place = places.setdefault(_PLACES[where], {"type": "object", "properties": {}, "required": []})
        place["properties"][name] = param.get("schema") or {}
        if where == "path" or param.get("required"):
            place["required"].append(name)
    properties: dict[str, Any] = dict(places)
    required = list(places)
    body = _resolve(spec, op.get("requestBody"))
    if isinstance(body, dict):
        content = body.get("content") or {}
        json_body = next((media for kind, media in content.items()
                          if kind.split(";")[0].strip() in ("application/json", "*/*")), None)
        if json_body is None:
            raise ValueError(f"{operation_id}: a body that is not JSON is not read")
        properties["body"] = json_body.get("schema") or {}
        if body.get("required"):
            required.append("body")
    for place in places.values():
        if not place["required"]:
            del place["required"]
    return {"title": operation_id, "type": "object", "properties": properties,
            "required": required, "additionalProperties": False}


def operation(spec: dict[str, Any], operation_id: str) -> Operation:
    """One operation and the language of the requests it accepts."""
    from .schema.adaptors.jsonschema import adapt
    path, method, _item, _op = _find(spec, operation_id)
    language = adapt(copy.deepcopy(request_schema(spec, operation_id)))
    return Operation(operation_id, method, path, language)


__all__ = ["Operation", "operation", "operation_ids", "request_schema"]
