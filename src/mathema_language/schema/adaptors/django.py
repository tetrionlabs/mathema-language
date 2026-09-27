# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A Django model as a row schema: its concrete fields with their
types, `null`, `blank`, `unique`, `choices`, `max_length`, the value
and length validators, and a `ForeignKey` as the `<name>_id` column
with a foreign key to the parent model; membership through
`full_clean`."""
from __future__ import annotations

import sys
from typing import Any

from ..ecosystems.django import DjangoEcosystem
from ..languages import RowLanguage
from ..model import Constraints, Field, ForeignKey, NeutralType, RowSchema, TableSchema

_INTS = {"SmallIntegerField": (16, None), "PositiveSmallIntegerField": (16, 0),
         "IntegerField": (32, None), "PositiveIntegerField": (32, 0),
         "BigIntegerField": (64, None), "PositiveBigIntegerField": (64, 0),
         "AutoField": (32, None), "BigAutoField": (64, None), "SmallAutoField": (16, None)}
_STRINGS = {"CharField", "SlugField", "EmailField", "URLField", "TextField", "UUIDField",
            "GenericIPAddressField", "FilePathField", "FileField", "ImageField"}
_SLUG = r"[-a-zA-Z0-9_]+"
_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


def _is_model(obj: Any) -> bool:
    """Whether `obj` is a concrete Django model class, decided
    without importing Django."""
    models = sys.modules.get("django.db.models")
    if models is None or not isinstance(obj, type):
        return False
    return issubclass(obj, models.Model) and not obj._meta.abstract  # type: ignore[attr-defined]


def _validator_constraints(validators: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for v in validators:
        code = getattr(v, "code", "")
        limit = getattr(v, "limit_value", None)
        if code == "min_value":
            out["min"] = limit
        elif code == "max_value":
            out["max"] = limit
        elif code == "min_length":
            out["min_len"] = limit
        elif code == "max_length":
            out["max_len"] = limit
        regex = getattr(v, "regex", None)
        if regex is not None and hasattr(regex, "pattern") and code == "invalid":
            out["regex"] = regex.pattern
    return out


def _field_of(f: Any) -> Field:
    kind = f.get_internal_type()
    constraints: dict[str, Any] = {}
    auto = kind in ("AutoField", "BigAutoField", "SmallAutoField")
    if kind in _INTS:
        bits, low = _INTS[kind]
        t = NeutralType("int", bits=bits)
        if low is not None:
            constraints["min"] = low
    elif kind == "FloatField":
        t = NeutralType("float")
    elif kind == "DecimalField":
        t = NeutralType("decimal", precision=f.max_digits, scale=f.decimal_places)
        if f.max_digits is not None:
            top = 10 ** (f.max_digits - (f.decimal_places or 0)) - 1
            constraints.update(min=-top, max=top)
    elif kind == "BooleanField":
        t = NeutralType("bool")
    elif kind == "DateTimeField":
        settings = sys.modules.get("django.conf")
        use_tz = bool(getattr(getattr(settings, "settings", None), "USE_TZ", True)) if settings else True
        t = NeutralType("datetime", tz="UTC" if use_tz else None)
    elif kind == "DateField":
        t = NeutralType("date")
    elif kind == "TimeField":
        t = NeutralType("time")
    elif kind == "DurationField":
        t = NeutralType("duration")
    elif kind == "BinaryField":
        t = NeutralType("binary")
    elif kind in ("ForeignKey", "OneToOneField"):
        t = NeutralType("int", bits=64)
    elif kind in _STRINGS:
        t = NeutralType("string")
        if getattr(f, "max_length", None):
            constraints["max_len"] = f.max_length
        if kind == "SlugField":
            constraints["regex"] = _SLUG
        elif kind == "UUIDField":
            constraints["regex"] = _UUID
    else:
        t = NeutralType("any")
    if f.choices:
        levels = tuple(value for value, _label in f.flatchoices)
        t = NeutralType("categorical", levels=levels)
    constraints.update(_validator_constraints(getattr(f, "validators", ())))
    if t.base == "string" and not f.blank and "min_len" not in constraints:
        constraints["min_len"] = 1
    nullable = bool(f.null) or auto
    return Field(f.attname, t, nullable=nullable, required=not (auto or f.has_default() or f.null),
                 unique=bool(f.unique) and not f.primary_key, constraints=Constraints(**constraints))


def _table_schema_of(model: type) -> TableSchema:
    """The table schema of a Django model."""
    fields = [_field_of(f) for f in model._meta.fields]  # type: ignore[attr-defined]
    foreign: list[ForeignKey] = []
    for f in model._meta.fields:  # type: ignore[attr-defined]
        if f.is_relation and f.related_model is not None:
            parent = f.related_model
            foreign.append(ForeignKey((f.attname,), parent.__name__, (parent._meta.pk.attname,)))
    pk = model._meta.pk  # type: ignore[attr-defined]
    return TableSchema(RowSchema(model.__name__, tuple(fields)),
                       primary_key=(pk.attname,) if pk is not None else (),
                       foreign_keys=tuple(foreign))


def adapt(obj: Any) -> RowLanguage | None:
    """The row language of a Django model, or None for anything else."""
    if not _is_model(obj):
        return None
    schema = _table_schema_of(obj)
    language = RowLanguage(schema.row, DjangoEcosystem(obj), obj.__name__)
    language._table_defaults = schema
    return language


__all__ = ["adapt"]
