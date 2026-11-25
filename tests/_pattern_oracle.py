# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""An independent reading of a pattern, kept beside the tests as an
oracle for the picture-to-term compiler: the picture read against a text
one character at a time, item by item, with no term and no regular
expression. A pattern's membership is its term's own matcher; the claims
here state that the two agree, on fixed pictures over any text, on
generated pictures over their own members, near misses and draws, and on
every vector picture."""
import random

from mathema_language.text import pattern as _pattern
from mathema_language.text._kit import TextLanguage
from mathema_language.text.pattern import Pattern, PatternError


def _ends(items, classes, text, starts):
    """The positions of `text` at which the items can end, having started
    at one of `starts`."""
    def once(item, at):
        atom = item.atom
        if isinstance(atom, _pattern._Group):
            return _ends(atom.items, classes, text, at)
        if isinstance(atom, _pattern._Class):
            return {p + 1 for p in at if p < len(text) and classes.has(atom.symbol, text[p])}
        literal = atom.text if isinstance(atom, _pattern._Run) else atom.char
        return {p + len(literal) for p in at if text.startswith(literal, p)}

    for item in items:
        now = starts
        for _ in range(item.lo):
            now = once(item, now)
        reached = set(now)
        taken = item.lo
        while now and (item.hi is None or taken < item.hi):
            now = once(item, now) - reached
            reached |= now
            taken += 1
        starts = reached
        if not starts:
            break
    return starts


def reads(pattern: Pattern, text: object) -> bool:
    """Whether `text` is a member of the pattern, by reading the picture
    against it one character at a time."""
    return isinstance(text, str) and len(text) in _ends(pattern._items, pattern._classes, text, {0})


def agrees(picture: str, base: str, text: str) -> bool:
    """Intent:
        Whether the pattern's membership (its term's own matcher) and the direct reading agree
        on `text`.

    Claims:
        a_postcode_agrees_on_any_text: for text in L[unicode], f("AA99[ ]9AA", "ascii", text) == True
        counted_groups_agree_on_any_text: for text in L[unicode], f("a{2,3}[ 9{1,2}]'b'", "ascii", text) == True
        unicode_classes_agree_on_any_text: for text in L[unicode], f("A{0+}9{0+}X{0,2}", "unicode", text) == True
        quoted_text_agrees_on_any_text: for text in L[unicode], f("'INV-'9{4}[-X{1,3}]", "ascii", text) == True
        a_bound_symbol_agrees_on_any_text: for text in L[unicode], f("AW{0,4}", "unicode", text) == True
    """
    pattern = Pattern(picture, base, W='lower + digit + "_"') if "W" in picture else Pattern(picture, base)
    return pattern.language().contains(text) == reads(pattern, text)


def agrees_on_its_own_texts(picture: str, base: str) -> bool:
    """Intent:
        Whether the term's membership and the direct reading agree on a pattern's members, its
        near misses, twenty draws and texts near it, for a picture drawn by `_PICTURES`.

    Claims:
        generated_ascii_pictures_agree: for picture in L[tests._pattern_oracle._PICTURES], f(picture, "ascii") == True
        generated_unicode_pictures_agree: for picture in L[tests._pattern_oracle._PICTURES], f(picture, "unicode") == True
        every_vector_picture_agrees_over_ascii: for picture in L[tests._pattern_oracle._VECTOR_PICTURES], f(picture, "ascii") == True
        every_vector_picture_agrees_over_unicode: for picture in L[tests._pattern_oracle._VECTOR_PICTURES], f(picture, "unicode") == True
    """
    try:
        pattern = Pattern(picture, base)
    except PatternError:
        return True
    rng = random.Random(picture + base)
    texts = set(pattern.members()) | {pattern.draw(rng) for _ in range(20)}
    texts |= {t for t, _ in pattern.near_misses(rng)}
    pool = "aZ9 -'[K.x_\\cdyé٣\n"
    texts |= {"".join(rng.choice(pool) for _ in range(rng.randint(0, 8))) for _ in range(20)}
    language = pattern.language()
    return all(language.contains(t) == reads(pattern, t) for t in texts)


#: pictures every reading of the notation is checked on: each construct alone and together
VECTORS = (
    "A", "a", "9", "X", "AA99", "AA99[ ]9AA", "'INV-'9{4}", "9{2,4}", "A{0+}", "A{1+}9{0,2}",
    "[-99]{2}", "[-99]{0,2}", "[[9]9]", "a{2,3}[ 9{1,2}]'b'", "\\[A\\]", "'a''b'", "'ab'{1}'cd'{2}",
    "'a-'{1}'cd'{2}", "X{7,8}", "A-'é'", "9{0+}X", "[A]{1,3}a", "' '{2}", "'ab'\\K'cd'{2}",
)


def _draw_picture(rng: random.Random, depth: int = 0) -> str:
    """One picture of one to four items drawn from the whole notation."""
    atoms = ["A", "a", "9", "X", "-", " ", "'ab'", "'K'", "'-.'", "\\[", "\\'", "\\K", "\\9", "'''", ".",
             "_", "'x''y'", "\\\\", "'cd'"]
    out = ""
    for _ in range(rng.randint(1, 4)):
        atom = "[" + _draw_picture(rng, depth + 1) + "]" if depth < 2 and rng.random() < 0.2 else rng.choice(atoms)
        roll = rng.random()
        if roll < 0.2:
            atom += f"{{{rng.randint(1, 3)}}}"
        elif roll < 0.3:
            lo = rng.randint(0, 2)
            atom += f"{{{lo},{lo + rng.randint(0 if lo else 1, 2)}}}"
        elif roll < 0.35:
            atom += f"{{{rng.randint(0, 2)}+}}"
        out += atom
    return out


def _is_short_picture(text: object) -> bool:
    """Whether `text` is a picture of at most `_LONGEST` characters that reads over ascii."""
    if not isinstance(text, str) or not 0 < len(text) <= _LONGEST:
        return False
    try:
        Pattern(text, "ascii")
    except (PatternError, ValueError):
        return False
    return True


#: the longest picture the generated pictures hold
_LONGEST = 48

_PICTURES = TextLanguage("generated pictures", level="predicate", accepts=_is_short_picture,
                         generate=_draw_picture)
_VECTOR_PICTURES = TextLanguage("vector pictures", level="predicate", accepts=lambda s: s in VECTORS,
                                generate=lambda rng: rng.choice(VECTORS))
