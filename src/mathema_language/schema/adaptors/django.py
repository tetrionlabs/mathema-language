# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A Django model as a record schema: its concrete fields with their
types, `null`, `blank`, `unique`, `choices`, `max_length` and the value
and length validators, a `ForeignKey` as its `<name>_id` column;
membership through `full_clean`."""
from __future__ import annotations

import sys
from typing import Any

from ...adaptor_priority import LIBRARY, priority
from ..ecosystems.django import DjangoEcosystem
from ..languages import RowLanguage
from ..model import Constraints, Field, NeutralType, RowSchema

_INTS = {"SmallIntegerField": (16, None), "PositiveSmallIntegerField": (16, 0),
         "IntegerField": (32, None), "PositiveIntegerField": (32, 0),
         "BigIntegerField": (64, None), "PositiveBigIntegerField": (64, 0),
         "AutoField": (32, None), "BigAutoField": (64, None), "SmallAutoField": (16, None)}
_STRINGS = {"CharField", "SlugField", "EmailField", "URLField", "TextField", "UUIDField",
            "GenericIPAddressField", "FilePathField", "FileField", "ImageField"}
_SLUG = r"[-a-zA-Z0-9_]+"
_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


def _is_model(obj: Any) -> bool:
    """Intent:
        Whether `obj` is a concrete (non-abstract) Django model class. False whenever
        `django.db.models` has not already been imported.
    """
    models = sys.modules.get("django.db.models")
    if models is None or not isinstance(obj, type):
        return False
    return issubclass(obj, models.Model) and not obj._meta.abstract  # type: ignore[attr-defined]


def _validator_constraints(validators: Any) -> dict[str, Any]:
    """Intent:
        The neutral constraints Django's value, length and regex validators spell, read from
        each validator's `code`, `limit_value` and `regex`.
    """
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
    """Intent:
        One neutral field from a Django model field: its type from the internal field type, with
        `null`, `blank`, `unique`, `choices`, `max_length` and validators read into the field.

    Notes:
        A foreign key becomes a 64-bit int column under its `attname` (`<name>_id`). An auto field
        is nullable and not required. A non-blank string field gets a minimum length of 1.
    """
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


def _row_schema_of(model: type) -> RowSchema:
    """Intent:
        The record schema of a Django model, one field per concrete field in `_meta.fields`.
    """
    fields = [_field_of(f) for f in model._meta.fields]  # type: ignore[attr-defined]
    return RowSchema(model.__name__, tuple(fields))


@priority(LIBRARY)
def adapt(obj: Any) -> RowLanguage | None:
    """The row language of a Django model, or None for anything else."""
    if not _is_model(obj):
        return None
    return RowLanguage(_row_schema_of(obj), DjangoEcosystem(obj), obj.__name__)


__all__ = ["adapt"]
