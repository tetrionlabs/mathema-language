# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The text languages: alphabets, predicate languages and the hazard
sub-alphabets, each a `Language` mathema resolves by the name in
`LANGUAGES`."""
from ._kit import TextLanguage
from .alphabets import (
    ALNUM,
    ALPHA,
    ASCII,
    C0,
    COMBINING,
    DIGIT,
    FORMAT,
    LATIN1,
    NFKC_FOLDING,
    NON_BMP,
    PRINTABLE,
    SURROGATE,
    UNICODE,
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
        UNICODE, ASCII, LATIN1, PRINTABLE, DIGIT, ALPHA, ALNUM,
        IDENTIFIER, JSON, UUID, ISO_DATE, ISO_DATETIME, IPV4, IPV6,
        BASE64, HEX, SLUG, SHELL_SAFE,
        C0, FORMAT, COMBINING, SURROGATE, NFKC_FOLDING, NON_BMP)}

__all__ = ["adapt", "ALNUM", "ALPHA", "ASCII", "BASE64", "C0", "COMBINING", "DIGIT",
           "FORMAT", "HEX", "IDENTIFIER", "IPV4", "IPV6", "ISO_DATE",
           "ISO_DATETIME", "JSON", "LANGUAGES", "LATIN1", "NFKC_FOLDING",
           "NON_BMP", "PRINTABLE", "SHELL_SAFE", "SLUG", "SURROGATE",
           "TEXT_HAZARDS", "TextLanguage", "UNICODE", "UUID"]


def adapt(hint: object) -> TextLanguage | None:
    """The language a text annotation names: every `str` for `str` and
    for `Annotated[str, ...]`, nothing for any other annotation.
    Registered under `mathema.language_adaptors` as `text`, so a `str`
    parameter with no stated domain infers `L[unicode]`."""
    import typing

    if hint is str:
        return UNICODE
    if typing.get_origin(hint) is typing.Annotated and typing.get_args(hint)[:1] == (str,):
        return UNICODE
    return None
