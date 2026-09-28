# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Text functions with the bugs the text hazards exist to find."""


def parse_quantity(text: str) -> int:
    """The quantity typed into a form, 0 when it is not a number."""
    return int(text) if text.isdigit() else 0


def json_keys(text: str) -> int:
    """How many keys a JSON document holds, counted recursively."""
    import json

    def keys(value) -> int:
        if isinstance(value, dict):
            return len(value) + sum(keys(v) for v in value.values())
        if isinstance(value, list):
            return sum(keys(v) for v in value)
        return 0

    return keys(json.loads(text))
