# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Language domains for mathema.

A claim quantifies a parameter over a language with `L[<name>]`, the
way it quantifies a number over `R` or `[0, 1]`. mathema itself parses,
renders and records the domain and resolves no name; this package
supplies the names: the languages of text and formats, the built-in
claims over text, and the languages of records a schema describes. Everything registers through mathema's entry-point groups, so
installing the package is the whole configuration.
"""
from ._surface import EXTENSION_API_VERSION

__version__ = "0.1.0"

SUPPORTED_EXTENSION_API = (1,)
if EXTENSION_API_VERSION not in SUPPORTED_EXTENSION_API:
    raise ImportError(
        f"mathema-language {__version__} needs mathema extension API "
        f"{SUPPORTED_EXTENSION_API}, found {EXTENSION_API_VERSION}")

__all__ = ["__version__", "SUPPORTED_EXTENSION_API"]
