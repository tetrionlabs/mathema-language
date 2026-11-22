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
claim spells it `L[path, within ("/workspace")]`. Given several roots it is
the union: an absolute path is at or under any one of them, spelled
`L[path, within ("/workspace", "/data")]`. It is decided on the
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


def _normal_roots(root: str, more: tuple[str, ...]) -> tuple[str, ...]:
    """Intent:
        The normalised forms of the roots, in the order given, each once.

    Raises:
        ValueError: a root is not an absolute path without a NUL or a `..` segment.
    """
    return tuple(dict.fromkeys(_normal_root(r) for r in (root, *more)))


def _absolute(root: str) -> str:
    """Intent:
        The regular expression of the absolute paths at or under the normalised `root` that
        name no `..` segment; under `/` that is every absolute path with none, `//a`
        included, as under any other root a doubled slash is read as part of the path.
    """
    return (r"/" + _SEGMENT + r"(?:/" + _SEGMENT + r")*" if root == "/"
            else re.escape(root) + r"(?:/" + _SEGMENT + r")*")


def within_pattern(root: str, *more: str) -> str:
    """The regular expression, read in full, of the paths `path_within`
    admits for `root`, or for the union of `root` and `more`.

    Raises:
        ValueError: a root is not an absolute path without a NUL or a `..` segment.
    """
    roots = _normal_roots(root, more)
    return r"(?:" + "|".join([_RELATIVE, *(_absolute(r) for r in roots)]) + r")"


#: the top-level directories an operating system keeps its own files, devices, users and
#: scratch space in (the Filesystem Hierarchy Standard's, and macOS's own)
SYSTEM_DIRECTORIES = frozenset({
    "bin", "boot", "dev", "etc", "home", "lib", "lib32", "lib64", "libx32", "media", "mnt",
    "opt", "proc", "root", "run", "sbin", "srv", "sys", "tmp", "usr", "var",
    "Applications", "Library", "Network", "System", "Users", "Volumes", "cores", "private"})


def _safe_beside(path: str) -> bool:
    """Intent:
        Whether an absolute path may be offered as a value outside a path language: none of
        its segments is `.` or `..`, and it is not at or under a system directory.
    """
    segments = path.split("/")[1:]
    return not any(s in (".", "..") for s in segments) and segments[0] not in SYSTEM_DIRECTORIES


def _near(roots: tuple[str, ...]) -> tuple[str, ...]:
    """Intent:
        Absolute paths just beside each root: a sibling whose name starts with the root's
        (`/workspace2` for `/workspace`) and the root's name cut short. None climbs through
        `.` or `..`, or names a place at or under a system directory (`/etc` beside
        `/etcd`), since a function under test may open or remove what it is given.
    """
    out: list[str] = []
    for root in roots:
        if root == "/":
            continue
        out += [root + "2", root + "x"]
        if len(posixpath.basename(root)) > 1:
            out.append(root[:-1])
    return tuple(p for p in dict.fromkeys(out) if _safe_beside(p))


@dataclass(frozen=True)
class PathLanguage(TextLanguage):
    """A path language defined by `pattern`, read in full. `near` are
    paths beside its boundary, offered as values outside it where the
    pattern refuses them."""
    pattern: str = PATH_PATTERN
    near: tuple[str, ...] = ()

    def contains(self, value: Any) -> bool:
        return isinstance(value, str) and re.fullmatch(self.pattern, value) is not None

    def hazards(self) -> tuple[HazardValue, ...]:
        """The paths code most often gets wrong, the ones this language
        admits."""
        own = [h for h in self.extra_hazards if self.contains(h.value)]
        seen = {h.value for h in own}
        return tuple(own) + tuple(h for h in super().hazards() if h.value not in seen)

    def definition(self) -> dict[str, Any]:
        """The regular-language term of this language: its pattern,
        read in full."""
        from . import _regular
        return _regular.term(self.pattern, 0, "matches")

    def to_json(self) -> dict[str, Any]:
        """The persisted form with the language's `definition`, the
        term of the strings `pattern` matches in full."""
        return {**super().to_json(), "definition": self.definition()}

    def outside(self, rng: random.Random) -> Any:
        order = [text for text, _ in _HAZARDS] + ["", "a\x00b", *self.near]
        rng.shuffle(order)
        for text in order:
            if not self.contains(text):
                return text
        return None


_POOL = "abc.xyz/-_ 0é"


def _generate(pattern: str, roots: tuple[str, ...] = ()) -> Any:
    """Intent:
        A generator of random paths matching `pattern` in full: one to four short segments,
        sometimes absolute, and under one of `roots` in half the draws when there are any,
        falling back to `a` after forty misses.
    """
    def draw(rng: random.Random) -> str:
        for _ in range(40):
            depth = rng.randint(1, 4)
            parts = ["".join(rng.choice(_POOL.replace("/", "")) for _ in range(rng.randint(1, 6)))
                     for _ in range(depth)]
            text = "/".join(parts)
            if roots and rng.random() < 0.5:
                text = rng.choice(roots).rstrip("/") + "/" + text
            elif rng.random() < 0.3:
                text = "/" + text
            if re.fullmatch(pattern, text):
                return text
        return "a"
    return draw


PATH = PathLanguage(
    "path", level="predicate", accepts=lambda s: re.fullmatch(PATH_PATTERN, s) is not None,
    generate=_generate(PATH_PATTERN), pool=_POOL, simplest="a", pattern=PATH_PATTERN,
    extra_hazards=tuple(HazardValue("text", text, note) for text, note in _HAZARDS))


def _quoted(text: str) -> str:
    """Intent:
        `text` between double quotes, as a region is written inside `within (...)`: a backslash
        and a double quote each take a backslash before them, and a character that does not
        print is written as its escape, so the text reads back as a string literal.
    """
    out = text.replace("\\", "\\\\").replace('"', '\\"')
    return '"' + "".join(c if c.isprintable() else c.encode("unicode_escape").decode("ascii")
                         for c in out) + '"'


def path_within(root: str, *more: str) -> PathLanguage:
    """The paths confined to `root`, which is an absolute path: relative
    paths with no `..` segment, and absolute paths that are `root` or lie
    under it, with no `..` segment. With `more` roots, the union: an
    absolute path is at or under any one of them.

    Raises:
        ValueError: a root is not an absolute path without a NUL or a `..` segment.
    """
    roots = _normal_roots(root, more)
    pattern = within_pattern(*roots)
    name = "path, within (" + ", ".join(_quoted(r) for r in roots) + ")"
    hazards = tuple(HazardValue("text", text, note) for text, note in _HAZARDS)
    hazards += tuple(HazardValue("text", r, "a root itself") for r in roots)
    hazards += tuple(HazardValue("text", r.rstrip("/") + "/", "a root with a trailing slash") for r in roots)
    return PathLanguage(
        name, level="predicate",
        accepts=lambda s: re.fullmatch(pattern, s) is not None, generate=_generate(pattern, roots),
        pool=_POOL, simplest="a", pattern=pattern, extra_hazards=hazards, near=_near(roots))


__all__ = ["PATH", "PATH_PATTERN", "PathLanguage", "path_within", "within_pattern"]
