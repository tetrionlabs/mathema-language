# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""`L[yaml]`: the texts that are one YAML document, read as YAML 1.2,
the current version of the spec, by ruamel.yaml's safe loader. In 1.2,
`no` is the string `'no'` and `012` is twelve. Which loader the code
under test uses is its own business; the language's hazards are the
texts that an older YAML 1.1 reader (PyYAML's `safe_load`) reads
differently, so a claim over `L[yaml]` exposes code that loads with one:
`country: no` is `False` there, `on: push` has the key `True`,
`mode: 012` is ten and `t: 1:20` is eighty. Every reader turns
`python: 3.10` into the float 3.1 and a bare date into a `date`.

Outside the language are the texts no YAML reader accepts: a tab in the
indentation, a key given twice, a mapping value after a mapping value
(`a: b: c`), an unclosed bracket, and two documents in one text."""
from __future__ import annotations

import random
import string
from dataclasses import dataclass
from typing import Any

from .._surface import HazardValue
from ._kit import TextLanguage

try:
    from ruamel.yaml import YAML
except ImportError as e:
    raise ImportError("L[yaml] reads YAML with ruamel.yaml, which is not installed: "
                      "pip install 'mathema-language[yaml]'") from e

_LOADER = YAML(typ="safe", pure=True)


def load(text: str) -> Any:
    """A YAML document read as YAML 1.2, the reference reading of
    `L[yaml]`: `no` is the string 'no', `012` is twelve."""
    return _LOADER.load(text)


def _is_yaml(text: str) -> bool:
    """Intent:
        Whether the YAML 1.2 safe loader reads `text` as one document.
    """
    try:
        _LOADER.load(text)
    except Exception:
        return False
    return True


#: scalars a person writes unquoted, several of which a YAML 1.1 reader
#: reads as something else
_SCALARS = ("no", "yes", "on", "off", "y", "n", "3.10", "012", "1:20", "1e3",
            "2026-10-10", "~", "null", "0x1A", ".nan", "true", "a", "plain text",
            "café", "日本語", "42", "-1", "1.5")

#: keys a person writes, the second one a YAML 1.1 boolean
_KEYS = ("name", "on", "version", "mode", "a", "key")


def _generate_yaml(rng: random.Random) -> str:
    """Intent:
        A small document written the way people write YAML: block mappings and lists,
        unquoted scalars, sometimes a comment.
    """
    lines: list[str] = []
    keys = rng.sample(_KEYS, rng.randint(1, 4))
    for key in keys:
        shape = rng.random()
        if shape < 0.6:
            comment = f"  # {rng.choice(['set by ops', 'see docs'])}" if rng.random() < 0.15 else ""
            lines.append(f"{key}: {rng.choice(_SCALARS)}{comment}")
        elif shape < 0.8:
            lines.append(f"{key}:")
            lines += [f"  - {rng.choice(_SCALARS)}" for _ in range(rng.randint(1, 3))]
        else:
            lines.append(f"{key}:")
            for inner in rng.sample(["x", "y", "z"], rng.randint(1, 2)):
                lines.append(f"  {inner}: {rng.choice(_SCALARS)}")
    return "\n".join(lines) + ("\n" if rng.random() < 0.8 else "")


#: valid YAML 1.2 that a YAML 1.1 reader reads differently, or that
#: every reader reads differently from what it looks like
_MISREAD = (
    ("country: no\n", "the Norway problem: False to a YAML 1.1 reader, 'no' in 1.2"),
    ("on: push\n", "a key a YAML 1.1 reader turns into True"),
    ("python: 3.10\n", "a version every reader turns into the float 3.1"),
    ("mode: 012\n", "octal ten to a YAML 1.1 reader, twelve in 1.2"),
    ("t: 1:20\n", "base sixty, eighty to a YAML 1.1 reader"),
    ("x: 1e3\n", "a float in 1.2, the string '1e3' to PyYAML"),
    ("released: 2026-10-10\n", "a date object, which json.dumps refuses"),
    ("v: ~\n", "null, written as a tilde"),
    ("v:\n", "null, written as nothing"),
    ("n: .nan\n", "NaN"),
    ("k: 0x1A\n", "hexadecimal twenty-six"),
    ("zip: 01234\n", "a leading zero, octal to a YAML 1.1 reader"),
    ("flag: Off\n", "False to a YAML 1.1 reader"),
    ("a: 1  # a comment\n", "a comment after a value"),
    ("\ufeffa: 1\n", "a byte-order mark before the document"),
    ("a: 1\r\nb: 2\r\n", "Windows line endings"),
    ("", "an empty document, which loads as null"),
    ("[" * 50 + "]" * 50 + "\n", "fifty nested flow lists"),
)

#: texts no YAML reader accepts
_REFUSED = ("a:\n\tb: 1\n", "a: 1\na: 2\n", "a: b: c\n", "key: [1, 2\n", "a: 1\n---\nb: 2\n",
            "- a\nb: 1\n", "a: 'unclosed\n")


@dataclass(frozen=True)
class YamlLanguage(TextLanguage):
    """`L[yaml]`, with the documents no YAML reader accepts as its
    outside values."""

    def hazards(self) -> tuple[HazardValue, ...]:
        """The documents a YAML 1.1 reader misreads first, then the shared
        text hazards that are documents too."""
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


YAML_TEXT = YamlLanguage(
    "yaml", level="predicate", accepts=_is_yaml, generate=_generate_yaml,
    pool=string.ascii_letters + string.digits + ": -#\n", simplest="a",
    extra_hazards=tuple(HazardValue("text", text, note) for text, note in _MISREAD))


__all__ = ["YAML_TEXT", "YamlLanguage", "load"]
