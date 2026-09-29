# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""What each schema library the adaptors read accepts for a missing
value, on the installed version. The adaptors' readings of holes and
absence rest on these; a release that changes one fails here first."""
import json
import math
import sqlite3
from decimal import Decimal

import pytest


def test_pydantic_float_fields_accept_nan_and_decimal_fields_refuse_it():
    pydantic = pytest.importorskip("pydantic")

    class M(pydantic.BaseModel):
        x: float = 0.0
        d: Decimal = Decimal(0)
        note: str | None = None

    assert math.isnan(M(x=math.nan).x)
    with pytest.raises(pydantic.ValidationError):
        M(d=Decimal("NaN"))


def test_pydantic_tells_a_field_never_set_from_one_set_to_none():
    pydantic = pytest.importorskip("pydantic")

    class M(pydantic.BaseModel):
        note: str | None = None

    assert "note" not in M().model_fields_set
    assert "note" in M(note=None).model_fields_set


def test_pydantic_validation_error_is_a_value_error():
    pydantic = pytest.importorskip("pydantic")
    assert issubclass(pydantic.ValidationError, ValueError)


def test_json_schema_numbers_accept_nan_and_null_is_distinct_from_a_missing_key():
    jsonschema = pytest.importorskip("jsonschema")
    schema = {"type": "object", "required": ["x"],
              "properties": {"x": {"type": "number"}, "y": {"type": ["string", "null"]}}}
    jsonschema.validate({"x": math.nan}, schema)
    jsonschema.validate({"x": 1, "y": None}, schema)
    jsonschema.validate({"x": 1}, schema)
    assert not issubclass(jsonschema.ValidationError, ValueError)


def test_json_text_carries_nan_only_as_a_non_standard_token():
    assert json.dumps({"x": math.nan}) == '{"x": NaN}'
    with pytest.raises(ValueError):
        json.dumps({"x": math.nan}, allow_nan=False)


def test_sqlite_stores_nan_as_null_and_refuses_it_in_a_not_null_column():
    db = sqlite3.connect(":memory:")
    db.execute("create table t (x real, y real not null)")
    db.execute("insert into t values (?, 1)", (math.nan,))
    assert db.execute("select x from t").fetchone() == (None,)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("insert into t values (1, ?)", (math.nan,))


def test_sqlalchemy_integrity_errors_are_not_value_errors():
    exc = pytest.importorskip("sqlalchemy.exc")
    assert not issubclass(exc.IntegrityError, ValueError)


def test_django_full_clean_accepts_nan_and_lets_none_through_only_a_blank_field():
    pytest.importorskip("django")
    import django
    from django.conf import settings
    if not settings.configured:
        settings.configure(INSTALLED_APPS=[])
        django.setup()
    from django.core.exceptions import ValidationError
    from django.db import models

    class Reading(models.Model):
        name = models.CharField(max_length=10)
        label = models.CharField(max_length=10, blank=True)
        value = models.FloatField()

        class Meta:
            app_label = "readings"

    Reading(name="a", value=math.nan).full_clean()
    with pytest.raises(ValidationError):
        Reading(name=None, value=1.0).full_clean()
    # a blank field skips validation of an empty value, None included,
    # though the column is NOT NULL and the database refuses it
    Reading(name="a", label=None, value=1.0).full_clean()
    assert not issubclass(ValidationError, ValueError)
