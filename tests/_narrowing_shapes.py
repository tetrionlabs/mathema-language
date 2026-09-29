# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Functions that refuse some inputs, and the languages narrowed to
what they accept, importable by dotted path for claims."""
from mathema_language.narrowing import narrow_language
from mathema_language.text import UNICODE


class Refused(Exception):
    """A library's own refusal, not a ValueError."""


def display_label(s: str) -> str:
    """s stripped, refused with a ValueError when nothing is left."""
    label = s.strip()
    if not label:
        raise ValueError(f"no label in {s!r}")
    return label


def ticket_code(s: str) -> str:
    """s upper-cased, refused with the library's own error when it holds
    no letter or digit."""
    if not any(c.isalnum() for c in s):
        raise Refused(s)
    return s.upper()


LABELS = narrow_language(UNICODE, display_label)
TICKET_CODES = narrow_language(UNICODE, ticket_code, errors=(Refused,))
