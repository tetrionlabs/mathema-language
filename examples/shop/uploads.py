# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The names uploaded files are stored under."""
from django.core.exceptions import SuspiciousFileOperation
from django.utils.text import get_valid_filename

from mathema_language.narrowing import narrow_language
from mathema_language.text import UNICODE


def upload_name(filename: str) -> str:
    """The name an uploaded file is stored under."""
    return get_valid_filename(filename)


UPLOAD_NAMES = narrow_language(UNICODE, upload_name, errors=(SuspiciousFileOperation,))
