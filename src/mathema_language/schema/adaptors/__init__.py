# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The adaptors, each turning one ecosystem's schema object into a
`RowLanguage` and answering "not mine" without importing that
ecosystem. Registered one per entry point under
`mathema.language_adaptors`; `adapt_row` tries them in order."""
from __future__ import annotations

from typing import Any

from ..languages import RowLanguage


def adapt_row(obj: Any) -> RowLanguage | None:
    """The row language of `obj` through the first adaptor that
    accepts it, or None."""
    from . import dataclass, typeddict
    for adapt in (dataclass.adapt, typeddict.adapt):
        language = adapt(obj)
        if language is not None:
            return language
    for name in ("pydantic", "jsonschema", "sqlalchemy", "django"):
        try:
            module = __import__(f"{__name__}.{name}", fromlist=["adapt"])
        except ImportError:
            continue
        adapted = module.adapt(obj)
        if isinstance(adapted, RowLanguage):
            return adapted
    return None


__all__ = ["adapt_row"]
