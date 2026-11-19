# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""`L[path]`: POSIX path text, any non-empty string without a NUL, the
way a program receives a path from a command line, a form or a config
file. Its hazards are the paths code that joins or splits them reads
wrongly: doubled and trailing slashes, a leading `./`, a newline or a
leading space in a name, names outside ASCII, and a name longer than
most filesystems allow. None names a real place or climbs out of the
directory it starts in, since a function under test may open or remove
what it is given.

`path_within(root)` is the language of paths confined to `root`: a
relative path with no `..` segment, or an absolute path that is the root
itself or starts with the root and a `/`, again with no `..` segment. A
claim spells it `L[path, within "/workspace"]`. It is decided on the
text, never by resolving it: `a/../b` stays inside the root but is
refused, since a rule that resolves `..` is not one an SMT solver can
decide, and a path that names what it means is the one to accept. It
says nothing about the filesystem: a symbolic link inside the root that
points outside it is not seen.

Both languages are defined by a regular expression, `pattern`, read in
full: membership is `re.fullmatch(pattern, text)`, and the z3 encoding
(`mathema_language.smt`) translates the same expression, so the two
agree by construction."""
from __future__ import annotations

import posixpath
import random
import re
from dataclasses import dataclass
from typing import Any

from .._surface import HazardValue
from ._kit import TextLanguage

#: one path segment that is not `..`: empty (a doubled slash), `.`, or
#: text that is neither `..` nor contains a slash or a NUL
_SEGMENT = r"(?:|\.|[^/.\x00][^/\x00]*|\.[^/.\x00][^/\x00]*|\.\.[^/\x00]+)"
_NONEMPTY_SEGMENT = r"(?:\.|[^/.\x00][^/\x00]*|\.[^/.\x00][^/\x00]*|\.\.[^/\x00]+)"
_RELATIVE = _NONEMPTY_SEGMENT + r"(?:/" + _SEGMENT + r")*"

#: any POSIX path text
PATH_PATTERN = r"[^\x00]+"

_HAZARDS = (
    ("a//b", "a doubled slash"),
    ("a/", "a trailing slash"),
    ("./a", "a leading './'"),
    ("a\nb", "a newline in a name"),
    (" a", "a leading space"),
    ("café/ü.txt", "names outside ASCII"),
    ("a" * 300, "a name longer than most filesystems allow"),
)


def _normal_root(root: str) -> str:
    """Intent:
        The normalised form of `root`, an absolute POSIX path with no `..` segment.

    Raises:
        ValueError: `root` is not a string, is not absolute, holds a NUL, or names a `..`
            segment.
    """
    if not isinstance(root, str) or not root.startswith("/") or "\x00" in root:
        raise ValueError(f"a root is an absolute path, not {root!r}")
    if ".." in root.split("/"):
        raise ValueError(f"a root names no '..' segment, not {root!r}")
    return posixpath.normpath(root) if root != "/" else "/"


def within_pattern(root: str) -> str:
    """The regular expression, read in full, of the paths `path_within`
    admits for `root`."""
    root = _normal_root(root)
    absolute = (r"/(?:" + _RELATIVE + r")?" if root == "/"
                else re.escape(root) + r"(?:/" + _SEGMENT + r")*")
    return r"(?:" + _RELATIVE + r"|" + absolute + r")"


@dataclass(frozen=True)
class PathLanguage(TextLanguage):
    """A path language defined by `pattern`, read in full."""
    pattern: str = PATH_PATTERN

    def contains(self, value: Any) -> bool:
        return isinstance(value, str) and re.fullmatch(self.pattern, value) is not None

    def hazards(self) -> tuple[HazardValue, ...]:
        """The paths code most often gets wrong, the ones this language
        admits."""
        own = [h for h in self.extra_hazards if self.contains(h.value)]
        seen = {h.value for h in own}
        return tuple(own) + tuple(h for h in super().hazards() if h.value not in seen)

    def outside(self, rng: random.Random) -> Any:
        order = [text for text, _ in _HAZARDS] + ["", "a\x00b"]
        rng.shuffle(order)
        for text in order:
            if not self.contains(text):
                return text
        return None


_POOL = "abc.xyz/-_ 0é"


def _generate(pattern: str) -> Any:
    """Intent:
        A generator of random paths matching `pattern` in full: one to four short segments,
        sometimes absolute, falling back to `a` after forty misses.
    """
    def draw(rng: random.Random) -> str:
        for _ in range(40):
            depth = rng.randint(1, 4)
            parts = ["".join(rng.choice(_POOL.replace("/", "")) for _ in range(rng.randint(1, 6)))
                     for _ in range(depth)]
            text = "/".join(parts)
            if rng.random() < 0.3:
                text = "/" + text
            if re.fullmatch(pattern, text):
                return text
        return "a"
    return draw


PATH = PathLanguage(
    "path", level="predicate", accepts=lambda s: re.fullmatch(PATH_PATTERN, s) is not None,
    generate=_generate(PATH_PATTERN), pool=_POOL, simplest="a", pattern=PATH_PATTERN,
    extra_hazards=tuple(HazardValue("text", text, note) for text, note in _HAZARDS))


def path_within(root: str) -> PathLanguage:
    """The paths confined to `root`, which is an absolute path: relative
    paths with no `..` segment, and absolute paths that are `root` or lie
    under it, with no `..` segment."""
    pattern = within_pattern(root)
    return PathLanguage(
        f'path, within "{_normal_root(root)}"', level="predicate",
        accepts=lambda s: re.fullmatch(pattern, s) is not None, generate=_generate(pattern),
        pool=_POOL, simplest="a", pattern=pattern,
        extra_hazards=tuple(HazardValue("text", text, note) for text, note in _HAZARDS))


__all__ = ["PATH", "PATH_PATTERN", "PathLanguage", "path_within", "within_pattern"]
