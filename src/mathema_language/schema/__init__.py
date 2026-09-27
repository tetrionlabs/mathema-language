# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The schema model behind `L[Order]`: one neutral description of a
record type (`RowSchema`), read off a dataclass, a TypedDict, a
pydantic model, a JSON Schema, a SQLAlchemy table or a Django model by
an adaptor, and the language over it, `RowLanguage`, whose members are
single records. An `Ecosystem` says what a record is in one library
and validates it with that library's own validator."""
from .ecosystems._base import Ecosystem
from .ecosystems.plain import AttributeEcosystem, PlainEcosystem
from .languages import NoMember, RowLanguage
from .model import (
    BASES,
    NO_DEFAULT,
    Constraints,
    Field,
    NeutralType,
    RowSchema,
)

__all__ = ["BASES", "NO_DEFAULT", "AttributeEcosystem", "Constraints", "Ecosystem",
           "Field", "NeutralType", "NoMember", "PlainEcosystem", "RowLanguage", "RowSchema"]
