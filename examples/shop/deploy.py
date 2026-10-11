# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The shop's deploy configuration, written by people in YAML."""
import yaml


def read_config(text: str) -> object:
    """A deploy configuration as the deploy tool reads it."""
    return yaml.safe_load(text)


def replicas(text: str) -> int:
    """How many copies of the service a configuration asks for, 1 when
    it does not say."""
    return int(yaml.safe_load(text).get("replicas", 1))
