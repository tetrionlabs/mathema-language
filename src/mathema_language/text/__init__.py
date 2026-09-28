# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The text languages (alphabets, formats, and the alphabets of
characters code usually gets wrong), each a `Language` mathema resolves
by the name in `LANGUAGES`, and the text vocabulary for claims:
`let nfkc = mathema_language.text.nfkc`."""
from typing import Any

from ..adaptor_priority import STRUCTURAL, priority
from ..vocabulary.text import (
    casefold,
    count,
    endswith,
    lower,
    nfc,
    nfc_len,
    nfd,
    nfkc,
    nfkd,
    splitlines,
    startswith,
    strip,
    upper,
    utf8_len,
)
from ._kit import TextLanguage
from .alphabets import (
    ALNUM,
    ALPHA,
    ASCII,
    ASTRAL,
    COMBINING,
    COMPATIBILITY,
    CONTROL,
    DIGIT,
    INVISIBLE,
    LATIN1,
    PRINTABLE,
    SURROGATE,
    UNICODE,
    UNICODE_ALNUM,
    UNICODE_ALPHA,
)
from .hazards import TEXT_HAZARDS
from .predicates import (
    BASE64,
    HEX,
    IDENTIFIER,
    IPV4,
    IPV6,
    ISO_DATE,
    ISO_DATETIME,
    JSON,
    SHELL_SAFE,
    SLUG,
    UUID,
)

#: every text language this package registers, by the name a claim writes
LANGUAGES: dict[str, TextLanguage] = {
    language.name: language for language in (
        UNICODE, ASCII, LATIN1, PRINTABLE, DIGIT, ALPHA, ALNUM, UNICODE_ALPHA, UNICODE_ALNUM,
        IDENTIFIER, JSON, UUID, ISO_DATE, ISO_DATETIME, IPV4, IPV6,
        BASE64, HEX, SLUG, SHELL_SAFE,
        CONTROL, INVISIBLE, COMBINING, SURROGATE, COMPATIBILITY, ASTRAL)}

__all__ = ["adapt", "ALNUM", "ALPHA", "ASCII", "BASE64", "CONTROL", "COMBINING", "DIGIT",
           "INVISIBLE", "HEX", "IDENTIFIER", "IPV4", "IPV6", "ISO_DATE",
           "ISO_DATETIME", "JSON", "LANGUAGES", "LATIN1", "COMPATIBILITY",
           "ASTRAL", "PRINTABLE", "SHELL_SAFE", "SLUG", "SURROGATE", "UNICODE_ALNUM", "UNICODE_ALPHA",
           "TEXT_HAZARDS", "TextLanguage", "UNICODE", "UUID",
           "casefold", "count", "endswith", "lower", "nfc", "nfc_len", "nfd", "nfkc", "nfkd", "splitlines", "startswith", "strip", "upper", "utf8_len"]


@priority(STRUCTURAL)
def adapt(hint: object) -> Any:
    """The language a text annotation names: every `str` for `str`, and
    for `Annotated[str, ...]` every `str` refined by the length markers
    it carries (`max_length`, `min_length`, read by attribute, as
    `annotated_types` and pydantic spell them), nothing for any other
    annotation.
    Registered under `mathema.language_adaptors` as `text`, so a `str`
    parameter with no stated domain infers `L[unicode]`."""
    import typing

    if hint is str:
        return UNICODE
    if typing.get_origin(hint) is typing.Annotated and typing.get_args(hint)[:1] == (str,):
        lo, hi = 0, None
        for marker in typing.get_args(hint)[1:]:
            found = getattr(marker, "max_length", None)
            if isinstance(found, int):
                hi = found if hi is None else min(hi, found)
            found = getattr(marker, "min_length", None)
            if isinstance(found, int):
                lo = max(lo, found)
        if hi is None and lo == 0:
            return UNICODE
        from ..refinements import length, length_bound
        return length(UNICODE, length_bound(lo, hi))
    return None
