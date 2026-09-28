# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The shop's JSON: settings files and the documents its API accepts."""
import json


def settings_keys(text: str) -> int:
    """How many keys a settings document holds, at every level."""
    return _keys(json.loads(text))


def _keys(value) -> int:
    if isinstance(value, dict):
        return len(value) + sum(_keys(v) for v in value.values())
    if isinstance(value, list):
        return sum(_keys(v) for v in value)
    return 0


def resave(text: str) -> str:
    """A settings document written back out after it is read."""
    return json.dumps(json.loads(text))
