# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The shop's text helpers: display names, headers, slugs, comment
rendering and config files."""
import html
import json
from typing import Annotated

from annotated_types import MaxLen


def display_name(username: str) -> str:
    """The username as shown in the header, upper-cased."""
    return username.upper()


def header_value(value: str) -> str:
    """The value as it goes on the wire in an HTTP header."""
    return value.encode("ascii").decode("ascii")


def slugify(title: str) -> str:
    """The title as a URL slug."""
    words, word = [], ""
    for ch in title.lower():
        if "a" <= ch <= "z" or "0" <= ch <= "9":
            word += ch
        elif word:
            words.append(word)
            word = ""
    if word:
        words.append(word)
    return "-".join(words)


def render_comment(body: str) -> str:
    """A comment body, safe to put in a page."""
    return html.escape(body)


def normalise_config(text: str) -> str:
    """A JSON config file with its keys sorted, as the repo stores it."""
    return json.dumps(json.loads(text), sort_keys=True, indent=2)


def short_title(title: Annotated[str, MaxLen(60)]) -> str:
    """The title, cut to the sixty characters the column holds."""
    return title[:60]


def username_key(name: str) -> str:
    """The key an account is stored under, so two spellings of a name
    find the same account."""
    return name.strip().lower()


def is_blank(name: str) -> bool:
    """Whether a display name has nothing visible in it."""
    return not name.strip()


def first_initial(name: str) -> str:
    """The avatar letter shown for a user."""
    return name[0].upper()


def to_bytes(text: str) -> bytes:
    """The text as the database driver sends it."""
    return text.encode("utf-8")


def js_length(text: str) -> int:
    """The length the browser's JavaScript reports for the text."""
    return len(text.encode("utf-16-le")) // 2


def log_line(message: str) -> str:
    """A message made safe to write to a log file."""
    return "".join(c for c in message if c.isprintable())


def note_header(note: str) -> str:
    """An HTTP header carrying a free-text note."""
    return "X-Note: " + note


def parse_quantity(text: str) -> int:
    """The quantity typed into a form, 0 when it is not a number."""
    return int(text) if text.isdigit() else 0
