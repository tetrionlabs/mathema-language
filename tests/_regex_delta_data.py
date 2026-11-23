# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Where regular-expression dialects and versions read a construct
differently, as data: the regex delta table.

`dump` runs, on the interpreter running it, every probe of every
construct: whether the pattern compiles, and for each probe text
whether it matches in full and where `search` finds it. `merge` joins
the dumps of every supported Python into the file the package ships.
A construct every version reads alike has no row and is listed under
`read_alike`, with the digest every version gives it under
`alike_digests`; a construct some version reads differently has one row
per version, keyed by construct, dialect and version, saying whether
that version reads it and a digest of how. Under `by_unicode`, the
constructs two Pythons read alike exactly when they share a Unicode
version. Under `flags`, each flag word maps to the name and inline
letter each dialect gives it. Unicode class membership and case
mapping are the version table's (`python_versions.json`), so the
probes use only characters every version classes alike. It uses the
standard library only, so any interpreter runs it bare:

    for v in 3.10 3.11 3.12 3.13 3.14; do
        uv run --python $v --no-project python tests/_regex_delta_data.py dump /tmp/rx-$v.json
    done
    uv run python tests/_regex_delta_data.py merge /tmp/rx-3.1*.json
"""
import hashlib
import json
import re
import sys
import warnings
from pathlib import Path

DATA = Path(__file__).parent.parent / "src" / "mathema_language" / "text" / "data" / "regex_deltas.json"

#: each construct, by its name in the table, with patterns that use it and flags they take
PROBES = {
    "literal": [("a", 0), (r"\.", 0), (r"\n", 0), (r"\x61", 0), (r"\u0061", 0), (r"\141", 0),
                (r"\N{LATIN SMALL LETTER A}", 0), ("ab", 0)],
    "any character": [(".", 0), ("a.b", 0)],
    "character set": [("[a-c]", 0), ("[^a]", 0), (r"[\d]", 0), ("[a-]", 0), (r"\d", 0),
                      (r"\w", 0), (r"\s", 0), (r"\D", 0), (r"\W", 0), (r"\S", 0), ("[]a]", 0),
                      ("[a&&b]", 0), ("[[a]", 0), ("[a--b]", 0), ("[a||b]", 0), ("[a~~b]", 0)],
    "alternation": [("a|b", 0), ("a|", 0), ("|b", 0)],
    "group": [("(a)", 0), ("(?:a)b", 0), ("(?P<n>a)", 0), ("()", 0)],
    "greedy repeat": [("a*", 0), ("a+", 0), ("a?", 0), ("a{2}", 0), ("a{1,2}", 0), ("a{,2}", 0),
                      ("a{2,}", 0), ("a{}", 0), ("a{x}", 0), ("(?:a*)*", 0)],
    "lazy repeat": [("a*?", 0), ("a+?", 0), ("a??", 0), ("a{1,2}?", 0)],
    "possessive repeat": [("a*+", 0), ("a++", 0), ("a?+", 0), ("a{1,2}+", 0), ("a*+a", 0)],
    "atomic group": [("(?>a+)", 0), ("(?>a+)a", 0)],
    "start of line": [("^a", 0), ("^a", re.M)],
    "end of line": [("a$", 0), ("a$", re.M)],
    "start of text": [(r"\Aa", 0)],
    "end of text": [(r"a\Z", 0)],
    "end of text, written \\z": [(r"a\z", 0)],
    "word boundary": [(r"\ba", 0), (r"a\b", 0), (r"\b", 0)],
    "not a word boundary": [(r"\Ba", 0), (r"a\B", 0), (r"\B", 0)],
    "backreference": [(r"(a)\1", 0), ("(?P<n>a)(?P=n)", 0)],
    "conditional": [("(a)?(?(1)b|c)", 0)],
    "lookahead": [("(?=a)a", 0), ("(?!a)b", 0)],
    "lookbehind": [("(?<=a)b", 0), ("(?<!a)b", 0)],
    "inline flags at the start": [("(?i)a", 0), ("(?im)a", 0), ("(?i)(?m)a", 0), ("(?x) a b", 0)],
    "inline flags after the start": [("a(?i)b", 0), ("(?:a)(?i)b", 0)],
    "scoped flags": [("(?i:a)b", 0), ("(?-i:a)b", re.I), ("(?s:.)", 0), ("(?a:\\w)", 0)],
    "ignore case": [("ab", re.I), ("[a-c]", re.I)],
    "multi line": [("^b", re.M)],
    "dot all": [(".", re.S)],
    "ascii only": [(r"\w", re.A)],
    "verbose": [("a b # c", re.X), ("[ ]a", re.X)],
    "named character": [(r"\N{LATIN SMALL LETTER A}", 0), (r"[\N{DIGIT ONE}]", 0), (r"\N{SHAKING FACE}", 0),
                        (r"\N{CJK UNIFIED IDEOGRAPH-2EBF0}", 0)],
    "group reference by a non-ASCII digit": [("(a)?(?(\u0661)b|c)", 0)],
    "group reference written loosely": [("(a)?(?(+1)b|c)", 0), ("(a)?(?( 1)b|c)", 0), ("(a)?(?(1 )b|c)", 0)],
}

TEXTS = ["", "a", "aa", "aaa", "b", "ab", "ba", "c", "bc", "abc", "A", "AB", "Ab", "a b", "\n",
         "a\n", "b\na", "1", "_", ".", "&", "-", "]", " a", "ab "]

#: each flag word, by dialect, with the name and inline letter that dialect gives it
FLAG_NAMES = {"python": {
    "ignore case": ["IGNORECASE", "i"], "multi line": ["MULTILINE", "m"], "dot all": ["DOTALL", "s"],
    "ascii only": ["ASCII", "a"], "verbose": ["VERBOSE", "x"]}}

#: constructs some version reads differently that the term's translation reads for each
#: version on its own, by the version table's engine reading named
TRANSLATED = {"not a word boundary": "not_boundary_in_empty"}

#: constructs whose reading follows the Unicode version alone: two Pythons with one Unicode
#: version read them alike, and any two Pythons with different ones may not, since a named
#: character is known only from the Unicode version that names it
BY_UNICODE = ["named character"]


def _reading(pattern, flags):
    """Whether the pattern compiles here, and its full match and search span on each text."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            compiled = re.compile(pattern, flags)
        except re.error:
            return ["refuses"]
    out = ["reads"]
    for text in TEXTS:
        found = compiled.search(text)
        out.append([compiled.fullmatch(text) is not None, None if found is None else list(found.span())])
    return out


def dump(path):
    version = f"{sys.version_info[0]}.{sys.version_info[1]}"
    readings = {}
    for construct, probes in PROBES.items():
        each = [_reading(p, f) for p, f in probes]
        readings[construct] = {
            "reads": all(r[0] == "reads" for r in each),
            "refuses": all(r[0] == "refuses" for r in each),
            "digest": hashlib.sha256(json.dumps(each).encode()).hexdigest()[:16]}
    Path(path).write_text(json.dumps({"python": version, "readings": readings}, indent=1))


def merge(paths):
    dumps = sorted((json.loads(Path(p).read_text()) for p in paths),
                   key=lambda d: tuple(int(x) for x in d["python"].split(".")))
    versions = [d["python"] for d in dumps]
    alike, rows, alike_digests = [], [], {}
    for construct in PROBES:
        seen = {d["python"]: d["readings"][construct] for d in dumps}
        if len({json.dumps(r, sort_keys=True) for r in seen.values()}) == 1:
            alike.append(construct)
            alike_digests[construct] = next(iter(seen.values()))["digest"]
            continue
        for version, r in seen.items():
            rows.append({"construct": construct, "dialect": "python", "version": version,
                         "reads": "all" if r["reads"] else "none" if r["refuses"] else "some",
                         "digest": r["digest"]})
    for word, (name, letter) in FLAG_NAMES["python"].items():
        assert getattr(re, name) == getattr(re, letter.upper()), word
    out = {"dialect": "python", "versions": versions, "read_alike": alike, "alike_digests": alike_digests,
           "rows": rows,
           "translated": TRANSLATED, "by_unicode": BY_UNICODE, "flags": FLAG_NAMES}
    DATA.write_text(json.dumps(out, indent=1, ensure_ascii=True) + "\n")
    print("versions", versions, "read alike", len(alike), "rows", len(rows),
          sorted({r["construct"] for r in rows}))


if __name__ == "__main__":
    if sys.argv[1] == "dump":
        dump(sys.argv[2])
    else:
        merge(sys.argv[2:])
