# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""`L[toml]`: the texts that are one TOML 1.0 document, read by the
standard library's `tomllib` (`tomli` before Python 3.11, the same
reader). TOML has one reading, so its hazards are the documents code
built on a TOML file most often mishandles once they are read: a date
or time, which comes back as a `datetime` object that `json.dumps`
refuses; `inf` and `nan`; an integer past 64 bits, which Python reads
and readers in other languages refuse; dotted keys and a quoted key
containing a dot, which nest differently; inline tables and arrays of
tables; `version = 3.10`, which is the float 3.1; and the string forms
that read differently from how they look.

Outside the language are the texts no TOML reader accepts: a key given
twice, a table declared twice, a value with a leading zero, a bare
word as a value, a trailing comma or a line break in an inline table,
a date that does not exist, and a byte-order mark."""
from __future__ import annotations

import random
import string
import sys
from dataclasses import dataclass
from typing import Any

from .._surface import HazardValue
from ._kit import TextLanguage

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError as e:
        raise ImportError("L[toml] reads TOML with tomli before Python 3.11, which is not "
                          "installed: pip install 'mathema-language[toml]'") from e


def load(text: str) -> dict[str, Any]:
    """A TOML document as `tomllib` reads it, the reading of `L[toml]`."""
    return tomllib.loads(text)


def _is_toml(text: str) -> bool:
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return False
    return True


#: values a person writes in a config file, each valid TOML
_VALUES = ('"a"', '"plain text"', '"café"', "'C:\\temp'", "42", "-1", "1_000", "0x1A",
           "1.5", "3.10", "1e3", "true", "false", "inf", "nan", "2026-10-10",
           "2026-10-10T09:00:00", "2026-10-10T09:00:00Z", "09:00:00", "[1, 2]",
           '["a", "b"]', "{ x = 1, y = 2 }", '""')

_KEYS = ("name", "version", "port", "debug", "owner", "a", '"a.b"', "server.host")


def _generate_toml(rng: random.Random) -> str:
    """A small document written the way people write config files: keys
    at the top, then a table or an array of tables, sometimes a
    comment."""
    lines: list[str] = []
    for key in rng.sample(_KEYS, rng.randint(1, 3)):
        comment = "  # set by ops" if rng.random() < 0.15 else ""
        lines.append(f"{key} = {rng.choice(_VALUES)}{comment}")
    shape = rng.random()
    if shape < 0.3:
        lines += ["", "[database]"]
        lines += [f"{k} = {rng.choice(_VALUES)}" for k in rng.sample(["host", "port", "user"], 2)]
    elif shape < 0.5:
        for _ in range(rng.randint(1, 2)):
            lines += ["", "[[items]]", f"sku = {rng.choice(_VALUES)}"]
    return "\n".join(lines) + ("\n" if rng.random() < 0.8 else "")


#: valid TOML that code reading it most often mishandles
_HAZARDS = (
    ("released = 2026-10-10\n", "a date, read as a datetime.date that json.dumps refuses"),
    ("at = 2026-10-10T09:00:00\n", "a local date and time, a datetime with no time zone"),
    ("at = 2026-10-10T09:00:00Z\n", "a date and time in UTC, a datetime with a time zone"),
    ("at = 2026-10-10 09:00:00+01:00\n", "a space in place of the T, and an offset"),
    ("opens = 09:00:00\n", "a time of day, a datetime.time"),
    ("version = 3.10\n", "a version written as a number, the float 3.1"),
    ("limit = inf\n", "infinity, which json.dumps writes as Infinity, not JSON"),
    ("ratio = nan\n", "NaN, which equals nothing, itself included"),
    ("id = 99999999999999999999\n", "an integer past 64 bits, refused by readers in other languages"),
    ("n = 1_000\n", "underscores between digits"),
    ("mask = 0o755\n", "an octal integer"),
    ("zero = -0.0\n", "negative zero"),
    ("server.host = \"db\"\n", "a dotted key, which nests as {'server': {'host': 'db'}}"),
    ("\"a.b\" = 1\n", "a quoted key containing a dot, which does not nest"),
    ("\"\" = 1\n", "an empty key"),
    ("point = { x = 1, y = 2 }\n", "an inline table"),
    ("[[items]]\nsku = \"a\"\n[[items]]\nsku = \"b\"\n", "an array of tables, a list of dicts"),
    ("mixed = [1, \"a\", 1.5]\n", "an array of mixed types, valid since TOML 1.0"),
    ("path = 'C:\\temp\\new'\n", "a literal string, where a backslash is a backslash"),
    ("s = \"\"\"\nline\"\"\"\n", "a multi-line string, whose first line break is dropped"),
    ("s = \"\"\"a \\\n   b\"\"\"\n", "a line-ending backslash, which joins the lines"),
    ("a = 1\r\nb = 2\r\n", "Windows line endings"),
    ("", "an empty document, which reads as an empty table"),
    ("a = 1 # a comment\n", "a comment after a value"),
)

#: texts no TOML reader accepts
_REFUSED = ("a = 1\na = 2\n", "[a]\nb = 1\n[a]\nc = 2\n", "a = 01\n", "a = hello\n",
            "a = { b = 1, }\n", "a = { b = 1,\n c = 2 }\n", "d = 2026-02-30\n",
            "\ufeffa = 1\n", "a = True\n", "a = \n", "a.b = 1\n[a]\nc = 2\n")


@dataclass(frozen=True)
class TomlLanguage(TextLanguage):
    """`L[toml]`, with the documents no TOML reader accepts as its
    outside values."""

    def hazards(self) -> tuple[HazardValue, ...]:
        """The documents code most often mishandles first, then the
        shared text hazards that are documents too."""
        own = [h for h in self.extra_hazards if self.contains(h.value)]
        seen = {h.value for h in own}
        return tuple(own) + tuple(h for h in super().hazards() if h.value not in seen)

    def outside(self, rng: random.Random) -> Any:
        order = list(_REFUSED)
        rng.shuffle(order)
        for text in order:
            if not self.contains(text):
                return text
        return super().outside(rng)


TOML_TEXT = TomlLanguage(
    "toml", level="predicate", accepts=_is_toml, generate=_generate_toml,
    pool=string.ascii_letters + string.digits + ' ="#[]\n', simplest="a",
    extra_hazards=tuple(HazardValue("text", text, note) for text, note in _HAZARDS))


__all__ = ["TOML_TEXT", "TomlLanguage", "load"]
