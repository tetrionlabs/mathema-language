# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The error a language or adaptor raises when a library it reads with is not installed.

:draft attribute names.

`missing_library` is the import name of the library, `extra` the mathema-language extra that
installs it and `distribution` the package that has the extra. A reader of the error needs no
import of this package: it reads the three attributes."""
from __future__ import annotations


class MissingLibrary(ImportError):
    """An optional library is not installed. :draft

    Attributes:
        missing_library: the import name, for example "ruamel.yaml".
        extra: the mathema-language extra that installs it, for example "yaml".
        distribution: always "mathema-language".
    """

    distribution = "mathema-language"

    def __init__(self, subject: str, library: str, extra: str, verb: str = "is read with") -> None:
        super().__init__(f"{subject} {verb} {library}, which is not installed; "
                         f"install mathema-language[{extra}]")
        self.missing_library = library
        self.extra = extra
