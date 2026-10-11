# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The shop's service settings, written by people in TOML and shown on
the status page as JSON."""
import json

import tomllib


def settings_json(text: str) -> str:
    """The settings a TOML file gives, as the JSON the status page
    shows."""
    return json.dumps(tomllib.loads(text))

