# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Markers for this package's tests."""


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "running_unicode: the test reads the running Python's Unicode tables (unicodedata, "
        "str.isalpha, \\d \\w \\s), so what it pins holds for that Unicode version; "
        "select with -m running_unicode")
