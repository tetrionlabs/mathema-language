# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The vocabulary a claim binds with `let`: the text and table
operations of the `mathema/language` dialect, each a plain function
carrying a neutral id in `__mathema_vocabulary__` so another runtime
can map it."""
from . import table, text

__all__ = ["table", "text"]
