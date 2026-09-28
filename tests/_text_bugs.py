# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Text functions with the bugs the text hazards exist to find."""


def parse_quantity(text: str) -> int:
    """The quantity typed into a form, 0 when it is not a number."""
    return int(text) if text.isdigit() else 0
