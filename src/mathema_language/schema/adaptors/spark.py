# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A Spark schema as a row schema: a `pyspark.sql.types.StructType`, or
the JSON Spark writes for one (`df.schema.jsonValue()`, the
`schemaString` of a Delta table's log), read into the neutral model
without importing pyspark. Members are dicts shaped like
`Row.asDict(recursive=True)`: every field present, a nested struct a
dict, an array a list, a map a dict. Membership is the neutral checker's
reading of the schema; Spark itself is not consulted."""
from __future__ import annotations

import re
from typing import Any

from ...adaptor_priority import DOCUMENT, priority
from ..ecosystems.spark import SparkEcosystem
from ..languages import RowLanguage
from ..model import Constraints, Field, NeutralType, RowSchema

#: the integer types and their widths in bits
_INTEGERS = {"byte": 8, "short": 16, "integer": 32, "long": 64}

_SCALARS = {
    "string": NeutralType("string"),
    "boolean": NeutralType("bool"),
    "binary": NeutralType("binary"),
    "date": NeutralType("date"),
    "timestamp": NeutralType("datetime"),
    "timestamp_ntz": NeutralType("datetime"),
    "float": NeutralType("float", bits=32),
    "double": NeutralType("float", bits=64),
}

_DECIMAL = re.compile(r"decimal\(\s*(\d+)\s*,\s*(\d+)\s*\)")
_CHAR_VARCHAR = re.compile(r"(?:var)?char\((\d+)\)")
#: the metadata key Spark records a CHAR or VARCHAR column's declared type under
_CHAR_VARCHAR_KEY = "__CHAR_VARCHAR_TYPE_STRING"


def _looks_like_spark_json(obj: Any) -> bool:
    """Intent:
        Whether `obj` is a dict with `type: struct` and a `fields` list, the JSON form Spark
        writes for a struct schema.
    """
    return isinstance(obj, dict) and obj.get("type") == "struct" and isinstance(obj.get("fields"), list)


def _is_struct_type(obj: Any) -> bool:
    """Intent:
        Whether `obj` is pyspark's `StructType`, recognised by its class name, its `pyspark.`
        module and a callable `jsonValue`, without importing pyspark.
    """
    cls = type(obj)
    return cls.__name__ == "StructType" and cls.__module__.startswith("pyspark.") \
        and callable(getattr(obj, "jsonValue", None))


def type_of(spark_type: Any) -> tuple[NeutralType, bool]:
    """`(neutral type, nan allowed)` of one Spark data type in its JSON
    form: a string for a simple type, a dict for an array, map, struct
    or user-defined type. A type with no neutral reading is `any`."""
    if isinstance(spark_type, str):
        name = spark_type.strip().lower()
        if name in _INTEGERS:
            return NeutralType("int", bits=_INTEGERS[name]), False
        if name in _SCALARS:
            return _SCALARS[name], name in ("float", "double")
        if name == "decimal":
            return NeutralType("decimal", precision=10, scale=0), False
        m = _DECIMAL.fullmatch(name)
        if m:
            return NeutralType("decimal", precision=int(m.group(1)), scale=int(m.group(2))), False
        if _CHAR_VARCHAR.fullmatch(name):
            return NeutralType("string"), False
        if name.startswith("interval day") or name == "interval":
            return NeutralType("duration"), False
        return NeutralType("any"), False
    if isinstance(spark_type, dict):
        kind = spark_type.get("type")
        if kind == "array":
            item, _ = type_of(spark_type.get("elementType"))
            return NeutralType("list", item=item,
                               nullable_items=bool(spark_type.get("containsNull", True))), False
        if kind == "map":
            key, _ = type_of(spark_type.get("keyType"))
            value, _ = type_of(spark_type.get("valueType"))
            return NeutralType("map", key=key, value=value,
                               nullable_items=bool(spark_type.get("valueContainsNull", True))), False
        if kind == "struct":
            return NeutralType("struct", fields=tuple(_fields(spark_type))), False
        if kind == "udt" and spark_type.get("sqlType") is not None:
            return type_of(spark_type["sqlType"])
    return NeutralType("any"), False


def _max_length(metadata: dict[str, Any]) -> int | None:
    """Intent:
        The declared length of a CHAR or VARCHAR column, read from the field's metadata, or None
        when the metadata declares none.

    Notes:
        Spark writes such a column's type as `string` and keeps the declared type in metadata.
    """
    declared = metadata.get(_CHAR_VARCHAR_KEY)
    if isinstance(declared, str):
        m = _CHAR_VARCHAR.fullmatch(declared.strip().lower())
        if m:
            return int(m.group(1))
    return None


def _fields(struct: dict[str, Any]) -> list[Field]:
    """Intent:
        One neutral field per entry of a struct's JSON `fields`, with its type, nullability,
        whether NaN is allowed, a CHAR/VARCHAR length bound, and its metadata.
    """
    out: list[Field] = []
    for spec in struct.get("fields", ()):
        metadata = spec.get("metadata") or {}
        t, nan_allowed = type_of(spec.get("type"))
        out.append(Field(str(spec["name"]), t, nullable=bool(spec.get("nullable", True)),
                         constraints=Constraints(max_len=_max_length(metadata)),
                         nan_allowed=nan_allowed,
                         metadata=tuple(sorted((str(k), v) for k, v in metadata.items()))))
    return out


def schema_of(schema: Any) -> RowSchema:
    """The row schema of a Spark `StructType` or its JSON form."""
    data = schema.jsonValue() if _is_struct_type(schema) else schema
    if not _looks_like_spark_json(data):
        raise TypeError(f"not a Spark struct schema: {schema!r}")
    return RowSchema("struct", tuple(_fields(data)), column_policy="exact")


@priority(DOCUMENT)
def adapt(obj: Any) -> RowLanguage | None:
    """The row language of a Spark schema, or None for anything else."""
    if not (_is_struct_type(obj) or _looks_like_spark_json(obj)):
        return None
    return RowLanguage(schema_of(obj), SparkEcosystem())


__all__ = ["adapt", "schema_of", "type_of"]
