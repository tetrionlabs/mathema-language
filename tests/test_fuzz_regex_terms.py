# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Every term built from a generated Python pattern is sound against the
running `re`: for the running version, an exact term admits exactly what
`re` admits under each predicate and a pair of bounds holds it between
them; for every supported version at once, the running version's
reading lies between the bounds (or is the exact term). Patterns are
drawn from fragments that reach the constructs versions read
differently: possessive repeats, atomic groups, inline flags, `\\z`,
named characters, odd counts and escapes. Seeded; a small budget by
default, the full one under `heavy`."""
import random
import re
import warnings

from mathema_language.text import _algebra, _regular
from tests import _fuzz

SEED = 7
FRAGMENTS = [
    "a", "b", "\\.", "\\B", "\\b", "^", "$", "\\A", "\\Z", "\\z", "(?i)", "(?m)", "(?s)", "(?x)", "(?a)", " ",
    "#c\n", "a*+", "a++", "b?+", "(?>a+)", "(?>a|ab)", "a{,2}", "a{1, 2}", "a{ 1,2}", "a{1 ,2}", "a{1,2 }",
    "a{,}", "\\N{LATIN SMALL LETTER A}", "[a-c]", "[^a]", "\\d", "\\w", "\\s", "\\W", "[\\b]", "[a&&b]",
    "[a--b]", "[[a]", "[]a]", ".", "\\x61", "\\141", "\\0", "(?i:a)", "(?-i:a)", "(?s:.)", "(?a:\\w)", "(?u)",
    "(?:a|b)", "(a)", "()", "(?P<n>a)", "(?P<é>a)", "(?P<n١>a)", "a*?", "a??", "\\u0061", "\\U00000061",
    "[\\d-z]", "[a-\\d]", "\\8", "(?#c)", "\\Ab", "a{2}{3}", "a**", "(?i)(?m)", "\\e", "\\c", "\\$", "[\\z]",
    "\\ ", "{", "}", "a{1}?", "a{1}+", "(?x:a b)", "(?-x:a b)", "[\\s\\S]", "(?i)K", "\\K", "\\p{L}",
    "(?<=a)", "\\Z\\z", "\\B\\B", "(?:)", "(?m:^)", "(?s)(?i)", "a|", "|",
]
TEXTS = ["", "a", "aa", "aaa", "b", "ab", "ba", "abc", "A", "Ab", "a b", " ", "\n", "a\n", "b\na", "1", "_", ".",
         "-", "]", "K", "\u212a", "\u017f", "é", "١", "aab", "a\nb", "\n\n", "ab ", "c", "z", "\x00", "$", "{",
         "a{1, 2}"]
MODES = {"matches": "fullmatch", "contains": "search", "starts with": "match", "ends with": "ends"}


def _patterns(n: int) -> list[str]:
    rng = random.Random(SEED)
    out: set[str] = set()
    while len(out) < n:
        out.add("".join(rng.choice(FRAGMENTS) for _ in range(rng.randint(1, 4))))
    return sorted(out)


def _running(compiled: re.Pattern, mode: str, text: str) -> bool:
    if mode == "ends":
        return any(compiled.fullmatch(text, i) is not None for i in range(len(text) + 1))
    return getattr(compiled, mode)(text) is not None


def _check(n: int) -> tuple[int, int, int]:
    built = refused = checked = 0
    versions = [_regular.RUNNING, None] if _regular.RUNNING in _regular.versions_data()["versions"] else [None]
    for pattern in _patterns(n):
        for flags in (0, re.IGNORECASE):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    compiled = re.compile(pattern, flags)
                except (re.error, OverflowError, RecursionError, ValueError):
                    compiled = None
            for version in versions:
                for predicate, mode in MODES.items():
                    try:
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            doc = _regular.term(pattern, flags, predicate, version=version)
                    except (_regular.NotRegular, ValueError, RecursionError):
                        refused += 1
                        continue
                    built += 1
                    assert compiled is not None, (pattern, flags, version, "built though re refuses it here")
                    for text in TEXTS:
                        checked += 1
                        here = _running(compiled, mode, text)
                        if doc["exact"]:
                            assert _algebra.member(doc, text) == here, (pattern, flags, version, predicate, text)
                        else:
                            low, high = _algebra.member(doc, text, "at_most"), _algebra.member(doc, text, "at_least")
                            assert (not low or here) and (not here or high), (pattern, flags, version, predicate, text)
    return built, refused, checked


def test_generated_patterns_build_only_sound_terms():
    built, refused, checked = _check(100)
    _fuzz.report("regex terms", SEED, built=built, refused=refused, texts=checked)
    assert built > 200


@_fuzz.heavy
def test_generated_patterns_build_only_sound_terms_at_full_size():
    built, refused, checked = _check(3000)
    _fuzz.report("regex terms, full", SEED, built=built, refused=refused, texts=checked)
    assert built > 6000
