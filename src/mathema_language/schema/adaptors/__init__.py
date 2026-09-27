# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The adaptors, each turning one ecosystem's schema object into a
`RowLanguage` and answering "not mine" without importing that
ecosystem. Each is an ordinary registration under
`mathema.language_adaptors`, and `adapt_row` asks the registry in
mathema's order (priority, then name), so an adaptor from another
package is found exactly as these are."""
from __future__ import annotations

from typing import Any

from ..._surface import Language, language_adaptors


def adapt_row(obj: Any) -> Language | None:
    """The row language of `obj` from the first registered adaptor, in
    mathema's order, that answers one (a language of kind `row`), or
    None. An adaptor that refuses the object raises, and the refusal
    reaches the caller."""
    for _name, adapt in language_adaptors():
        language = adapt(obj)
        if language is not None and getattr(language, "kind", None) == "row":
            return language
    return None


__all__ = ["adapt_row"]
