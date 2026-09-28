# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The Django ecosystem: a record is an unsaved instance of the model.
The neutral checker holds types, then `full_clean` holds the field
options and validators; uniqueness and foreign keys, which need a
database in Django, are facts about many records and not checked on
one. Django is imported inside the methods that need it, never at
module level."""
from __future__ import annotations

from typing import Any

from ..._surface import Problem
from ..checks import row_problems
from ..model import RowSchema


class DjangoEcosystem:
    """Records are instances of `model`."""

    name = "django"

    def __init__(self, model: type) -> None:
        self.model = model

    def accepts(self, obj: Any) -> bool:
        return obj is self.model

    def to_model(self, obj: Any) -> RowSchema:
        from ..adaptors.django import _row_schema_of
        return _row_schema_of(obj)

    def _attnames(self) -> tuple[str, ...]:
        return tuple(f.attname for f in self.model._meta.fields)  # type: ignore[attr-defined]

    def _relation_names(self) -> list[str]:
        return [f.name for f in self.model._meta.fields if f.is_relation]  # type: ignore[attr-defined]

    def build_row(self, schema: RowSchema, values: dict[str, Any]) -> Any:
        return self.model(**values)

    def values(self, row: Any) -> dict[str, Any]:
        return {name: getattr(row, name, None) for name in self._attnames()}

    def validate_row(self, schema: RowSchema, row: Any) -> list[Problem]:
        from django.core.exceptions import ValidationError
        if not isinstance(row, self.model):
            return [Problem("", f"an instance of {self.model.__name__}", row)]
        values = self.values(row)
        neutral = row_problems(schema, values, columns=lambda _row: None)
        if neutral:
            return neutral
        instance: Any = row
        try:
            instance.full_clean(exclude=self._relation_names(), validate_unique=False)
        except ValidationError as e:
            out: list[Problem] = []
            for field_name, messages in e.message_dict.items():
                path = "" if field_name == "__all__" else f".{field_name}"
                for message in messages:
                    out.append(Problem(path, message, values.get(field_name)))
            return out
        return []


__all__ = ["DjangoEcosystem"]
