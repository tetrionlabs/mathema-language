# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""`explain` reads a regular-language term out in plain words. The
wording is pinned here on patterns under each predicate, the package's
own validators among them, and on shapes: sequences, repeats by their
counts, choices, character sets by range, by name and by what they leave
out, the final newline `$` allows, and a term stated as bounds, which
says what made it approximate. Terms with one canonical form read the
same, and no reading dumps a large set."""
import re

import pytest

from mathema_language.text import _regular
from mathema_language.text.explain import describe_characters, explain, explain_node
from mathema_language.text.shape import Shape

#: the sizes of the Unicode classes on the running Python, which a reading states
SIZES = {
    "digits": sum(chr(c).isdecimal() for c in range(0x110000)),
    "letters": sum(chr(c).isalpha() for c in range(0x110000)),
    "space": sum(chr(c).isspace() for c in range(0x110000)),
    "word": sum(chr(c).isalnum() or chr(c) == "_" for c in range(0x110000)),
}

#: name, pattern, flags, predicate, the reading
PATTERNS = [
    ('the example', '^[a-z0-9]+(?:-[a-z0-9]+)*$', 0, 'starts with',
     'one or more of: 0-9, a-z; then any number of: "-" followed by one or more of: 0-9, a-z; also accepts one final newline'),
    ('the example in full', '^[a-z0-9]+(?:-[a-z0-9]+)*$', 0, 'matches',
     'one or more of: 0-9, a-z; then any number of: "-" followed by one or more of: 0-9, a-z'),
    ('own: slug', '[a-z0-9]+(?:-[a-z0-9]+)*', 0, 'matches',
     'one or more of: 0-9, a-z; then any number of: "-" followed by one or more of: 0-9, a-z'),
    ('own: shell_safe', '[A-Za-z0-9@%_\\-+=:,./]+', 0, 'matches',
     'one or more of: "%", "+" to ":", "=", "@" to "Z", "_", a-z'),
    ('own: path', '[^\\x00]+', 0, 'matches',
     'one or more of: any character except: U+0000'),
    ('own: django slug', '[-a-zA-Z0-9_]+', 0, 'matches',
     'one or more of: "-", 0-9, A-Z, "_", a-z'),
    ('own: django uuid', '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', 0, 'matches',
     'exactly 8 of: 0-9, a-f; then "-"; then exactly 4 of: 0-9, a-f; then "-"; then exactly 4 of: 0-9, a-f; then "-"; then exactly 4 of: 0-9, a-f; then "-"; then exactly 12 of: 0-9, a-f'),
    ('unicode digits', '\\d+', 0, 'matches',
     'one or more of: digits (Unicode, {digits} characters)'),
    ('ascii digits', '[0-9]{3}-[0-9]{4}', 0, 'matches',
     'exactly 3 of: 0-9; then "-"; then exactly 4 of: 0-9'),
    ('word characters', '\\w+', 0, 'matches',
     'one or more of: word characters (Unicode, {word} characters)'),
    ('whitespace', '\\s*', 0, 'matches',
     'any number of: whitespace (Unicode, {space} characters)'),
    ('ascii letters', '[A-Za-z]+', 0, 'matches',
     'one or more of: ASCII letters'),
    ('a class and more', '[^\\W\\d_]+', 0, 'matches',
     'one or more of: letters (Unicode, {letters} characters)'),
    ('literal choice', 'a|b|cd', 0, 'matches',
     'one of: "a", "b", "cd"'),
    ('counts', 'a?b{2,3}(c|de)?', 0, 'matches',
     'optionally: "a"; then 2 to 3 of: "b"; then optionally: (one of: "c", "de")'),
    ('choice in a repeat', '(?:ab|c+)*d', 0, 'matches',
     'any number of: (either "ab" or (one or more of: "c")); then "d"'),
    ('optional letter', 'colou?r', 0, 'matches',
     '"colo"; then optionally: "u"; then "r"'),
    ('starts with', 'http://', 0, 'starts with',
     '"http://"; then any text'),
    ('ends with', '\\.csv', 0, 'ends with',
     'any text; then ".csv"'),
    ('contains', 'error', 0, 'contains',
     'any text; then "error"; then any text'),
    ('contains to the end', '[a-z]+$', 0, 'contains',
     'any text; then one or more of: a-z; also accepts one final newline'),
    ('dot', '.*', 0, 'matches',
     'any number of: any character except: newline'),
    ('dot all', '.+', 16, 'matches',
     'any text of 1 or more characters'),
    ('bounded line', '[^\\n]{1,80}', 0, 'matches',
     '1 to 80 of: any character except: newline'),
    ('a segment', '[^/\\x00]+', 0, 'matches',
     'one or more of: any character except: U+0000, "/"'),
    ('ignore case', 'k', 2, 'matches',
     'one of: "K", "k", "K" (U+212A)'),
    ('empty pattern', '', 0, 'matches',
     'the empty text'),
    ('backreference', '(a)\\1', 0, 'matches',
     'approximate because the pattern uses a backreference; every accepted text fits: "aa"; not every text that fits is accepted; no text is known to be accepted for certain'),
    ('lookahead', '(?=a)[a-z]+', 0, 'matches',
     'approximate because the pattern uses a lookahead; every accepted text fits: one or more of: a-z; not every text that fits is accepted; no text is known to be accepted for certain'),
    ('multi line', '(?m)^a$', 0, 'contains',
     'optionally: any text followed by "\\n"; then "a"; then optionally: "\\n" followed by any text'),
    ('word boundary', '\\bfoo\\b', 0, 'contains',
     'optionally: any text followed by any character except: word characters (Unicode, {word} characters); then "foo"; then optionally: (any character except: word characters (Unicode, {word} characters)) followed by any text'),
    ('named characters', '[ \\t]+x{0,4}', 0, 'matches',
     'one or more of: tab, space; then up to 4 of: "x"'),
    ('nested repeats', '(?:(?:ab)+c)+', 0, 'matches',
     'one or more of: (one or more of: "ab") followed by "c"'),
    ('control characters', '[\\x00-\\x1f]', 0, 'matches',
     'one of: U+0000 to U+001F'),
    ('identifier', '[a-zA-Z_][a-zA-Z0-9_]*', 0, 'matches',
     'one of: A-Z, "_", a-z; then any number of: 0-9, A-Z, "_", a-z'),
    ('deeper sequence', '(?:a(?:b[0-9]+c)*d)+', 0, 'matches',
     'one or more of: "a" followed by (any number of: ("b" followed by (one or more of: 0-9) followed by "c")) followed by "d"'),
    ('optional sequence', '[0-9]+(?:\\.[0-9]+)?', 0, 'matches',
     'one or more of: 0-9; then optionally: "." followed by one or more of: 0-9'),
    ('no match', '[^\\s\\S]', 0, 'matches',
     'nothing (no text is accepted)'),
]

#: shape, base, the reading
SHAPES = [
    ('AA99[ ]9AA', 'ascii',
     'exactly 2 of: ASCII letters; then exactly 2 of: 0-9; then optionally: " "; then one of: 0-9; then exactly 2 of: ASCII letters'),
    ('ID-9{4,6}', 'ascii',
     '"ID-"; then 4 to 6 of: 0-9'),
    ('A{1+}-9{2}', 'unicode',
     'one or more of: letters (Unicode, {letters} characters); then "-"; then exactly 2 of: digits (Unicode, {digits} characters)'),
    ('X{0+}', 'unicode',
     'any text'),
    ('a{2,3}[ 9{1,2}]b', 'ascii',
     '2 to 3 of: a-z; then optionally: " " followed by 1 to 2 of: 0-9; then "b"'),
]


@pytest.mark.parametrize("name, pattern, flags, predicate, reading", PATTERNS, ids=[p[0] for p in PATTERNS])
def test_a_pattern_reads_in_plain_words(name, pattern, flags, predicate, reading):
    said = explain(_regular.term(pattern, flags, predicate))
    if name == "a class and more":
        assert said.startswith(reading.format(**SIZES) + ', "\u00b2" (U+00B2), "\u00b3" (U+00B3), ')
        assert re.search(r", [0-9]+ more characters$", said) and said.count(",") <= 12
    else:
        assert said == reading.format(**SIZES)


@pytest.mark.parametrize("shape, base, reading", SHAPES, ids=[s[0] for s in SHAPES])
def test_a_shape_reads_in_plain_words(shape, base, reading):
    assert explain(Shape(shape, base).term()) == reading.format(**SIZES)


def test_there_are_at_least_twenty_five_pinned_readings_and_the_package_own_validators_among_them():
    assert len(PATTERNS) >= 25
    assert sum(name.startswith("own: ") for name, *_ in PATTERNS) >= 5


def test_the_path_within_pattern_reads_as_a_choice_between_a_relative_path_and_the_root():
    from mathema_language.text.path_language import within_pattern
    said = explain(_regular.term(within_pattern("/ws"), 0, "matches"))
    assert said.startswith('either ((either "." or ((any character except: U+0000, ".", "/") followed by ')
    assert ' or ("/ws" followed by any number of: ("/" followed by (optionally: either "." or ' in said
    assert said.count("(") == said.count(")")


@pytest.mark.parametrize("one, other", [
    (r"[a-z0-9]+", r"[0-9a-z]+"), (r"a{1,}", r"a+"), (r"(?:a|b)c", r"[ab]c"), (r"\Aab\Z", r"ab"),
    (r"[0-9][0-9]", r"[0-9]{2}"), (r"x(?:y)?", r"xy?"), (r"(?i)k", r"[Kk\u212a]"),
])
def test_terms_with_one_canonical_form_read_the_same(one, other):
    a, b = _regular.term(one, 0, "matches"), _regular.term(other, 0, "matches")
    if _regular.term_hash(a) == _regular.term_hash(b):
        assert explain(a) == explain(b)
    assert explain(a) == explain(dict(a, source={})) == explain_node(a["language"])
    assert explain(a) == explain({**a, "language": _regular.canonical(a["language"])})


def test_equal_readings_follow_from_equal_hashes_on_generated_patterns():
    import random
    rng = random.Random(31)
    pieces = ["a", "b", "[a-c]", "[0-9]", "x?", "(?:ab)*", "[^a]", ".", "\\d", "(?:a|bc)", "a{2,3}", "\\s+"]
    seen: dict[str, str] = {}
    for _ in range(300):
        pattern = "".join(rng.choice(pieces) for _ in range(rng.randint(1, 4)))
        doc = _regular.term(pattern, 0, rng.choice(["matches", "contains", "starts with", "ends with"]))
        said = explain(doc)
        assert seen.setdefault(_regular.term_hash(doc), said) == said
        assert len(said) < 2000


def test_a_term_stated_as_bounds_reads_each_bound_for_what_it_is():
    doc = _regular.term(r"(a|b)\1x", 0, "matches")
    assert doc["exact"] is False
    assert explain(doc) == ('approximate because the pattern uses a backreference; every accepted text fits: '
                            'exactly 2 of: "a", "b"; then "x"; not every text that fits is accepted; '
                            'no text is known to be accepted for certain')
    pair = {"kind": "regular_language", "version": 1, "alphabet": [[0, 1114111]], "exact": False,
            "at_least": {"op": "repeat", "arg": {"op": "chars", "ranges": [[48, 57]]}, "min": 1, "max": None},
            "at_most": {"op": "literal", "text": "0"},
            "source": {"not_exact": ["an interval of datetimes", "a lookbehind"]}}
    assert explain(pair) == ('approximate because the pattern uses an interval of datetimes and a lookbehind; '
                             'every accepted text fits: one or more of: 0-9; not every text that fits is '
                             'accepted; certainly accepted: "0"')
    assert explain({**pair, "source": {}}).startswith("approximate; every accepted text fits: ")


@pytest.mark.parametrize("ranges, said", [
    ([[0, 0x10FFFF]], "any character"), ([[48, 57]], "0-9"), ([[97, 122], [48, 57]], "0-9, a-z"),
    ([[65, 90], [97, 122]], "ASCII letters"), ([[32, 32], [9, 10]], "tab, newline, space"),
    ([[0, 9], [11, 0x10FFFF]], "any character except: newline"), ([[45, 45]], '"-"'), ([[34, 34]], '"\\""'),
    ([[0xE9, 0xE9]], '"\u00e9" (U+00E9)'), ([[0xD800, 0xDFFF]], "U+D800 to U+DFFF"),
    ([[97, 98]], '"a", "b"'), ([[97, 99]], "a-c"), ([[33, 47]], '"!" to "/"'),
    ([[i, i] for i in range(0x4E00, 0x4E00 + 40, 2)],
     ", ".join(f'"{chr(c)}" (U+{c:04X})' for c in range(0x4E00, 0x4E10, 2)) + ", 12 more characters"),
])
def test_a_character_set_reads_compactly(ranges, said):
    assert describe_characters(ranges) == said


def test_a_named_class_reads_by_name_with_its_size_and_never_as_a_dump():
    for pattern, name, size in [(r"\d", "digits", SIZES["digits"]), (r"\s", "whitespace", SIZES["space"]),
                                (r"\w", "word characters", SIZES["word"])]:
        ranges = _regular._class_chars(pattern)
        assert describe_characters(ranges) == f"{name} (Unicode, {size} characters)"
        assert describe_characters(_regular._cs_complement(ranges)) == (
            f"any character except: {name} (Unicode, {size} characters)")
    letters = [[lo, hi] for lo, hi in Shape("A").term()["language"]["ranges"]]
    assert describe_characters(letters) == f"letters (Unicode, {SIZES['letters']} characters)"
    assert describe_characters(letters + [[0x30, 0x39]]) == (
        f"letters (Unicode, {SIZES['letters']} characters), 0-9")


def test_explain_reads_only_a_term():
    with pytest.raises(ValueError):
        explain({"op": "literal", "text": "a"})
    with pytest.raises(ValueError):
        explain({"kind": "regular_language", "exact": False})
    with pytest.raises(ValueError):
        explain_node({"op": "star"})
