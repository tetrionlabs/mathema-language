# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Functions whose output length differs from their input's on some
characters, for the tests on length bounds."""


def display_name(username: str) -> str:
    """The username as shown in the header, upper-cased."""
    return username.upper()
