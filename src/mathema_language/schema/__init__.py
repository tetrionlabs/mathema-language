# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The schema model behind `L[Order]` and `L[ORDERS]`: one neutral
description of a record type (`RowSchema`) or a table of them
(`TableSchema`), read off a dataclass, a TypedDict, a pydantic model
or a JSON Schema by an adaptor, and two languages over it, `RowLanguage`
(a member is one record) and `FrameLanguage` (a member is a table).
An `Ecosystem` says what a record and a table are in one library and
validates them with that library's own validator."""
from .ecosystems._base import Ecosystem
from .ecosystems.plain import AttributeEcosystem, PlainEcosystem
from .languages import FrameLanguage, NoMember, RowLanguage, frame_of
from .model import (
    BASES,
    NO_DEFAULT,
    Constraints,
    Field,
    ForeignKey,
    NeutralType,
    RowSchema,
    TableSchema,
)

__all__ = ["BASES", "NO_DEFAULT", "AttributeEcosystem", "Constraints", "Ecosystem",
           "Field", "ForeignKey", "FrameLanguage", "NeutralType", "NoMember",
           "PlainEcosystem", "RowLanguage", "RowSchema", "TableSchema", "frame_of"]
