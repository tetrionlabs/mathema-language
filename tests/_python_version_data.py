# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""What each supported Python reads differently in a regular expression,
as data.

`dump` records, for the interpreter running it, its Unicode version, the
code points of each class whose members depend on that version (`\\d`,
`\\w`, `\\s` as `re` reads them, and the Unicode-wide alphabets), its case
mappings, the unassigned code points, and the engine readings that have
changed between versions. `merge` joins the dumps of every supported
version into the file the package ships: for each class the code points
every version holds and what each version adds, the code points
unassigned in the newest, and the code points whose case reading differs
between versions. It uses the standard library only, so any interpreter
runs it bare:

    for v in 3.10 3.11 3.12 3.13 3.14; do
        uv run --python $v --no-project python tests/_python_version_data.py dump /tmp/$v.json
    done
    uv run python tests/_python_version_data.py merge /tmp/3.1*.json
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

DATA = Path(__file__).parent.parent / "src" / "mathema_language" / "text" / "data" / "python_versions.json"
LAST = 0x10FFFF
MARKS = ("Mn", "Mc", "Me")

CLASSES = {
    "decimal": str.isdecimal,
    "word": lambda c: c.isalnum() or c == "_",
    "space": str.isspace,
    "printable": str.isprintable,
    "unicode_alpha": str.isalpha,
    "unicode_alnum": str.isalnum,
    "invisible": lambda c: unicodedata.category(c) == "Cf",
    "combining": lambda c: unicodedata.category(c) in MARKS,
    "compatibility": lambda c: unicodedata.normalize("NFKC", c) != c,
    "lowercase_letter": lambda c: unicodedata.category(c) == "Ll",
}


def ranges(codes):
    """Sorted code points as inclusive ranges."""
    out = []
    for code in codes:
        if out and out[-1][1] == code - 1:
            out[-1][1] = code
        else:
            out.append([code, code])
    return out


def points(spans):
    return {c for lo, hi in spans for c in range(lo, hi + 1)}


def dump():
    """What this interpreter reads."""
    every = [chr(c) for c in range(LAST + 1)]
    try:
        from re import _casefix
        casefix = {str(k): list(v) for k, v in _casefix._EXTRA_CASES.items()}
    except ImportError:
        import sre_compile
        casefix = {}
        for group in sre_compile._equivalences:
            for code in group:
                casefix[str(code)] = [c for c in group if c != code]
    return {
        "python": f"{sys.version_info[0]}.{sys.version_info[1]}", "release": sys.version.split()[0],
        "unicode": unicodedata.unidata_version,
        "classes": {name: ranges([c for c in range(LAST + 1) if inside(every[c])])
                    for name, inside in CLASSES.items()},
        "unassigned": ranges([c for c in range(LAST + 1) if unicodedata.category(every[c]) == "Cn"]),
        "lower": {str(c): ord(every[c].lower()) for c in range(LAST + 1)
                  if len(every[c].lower()) == 1 and every[c].lower() != every[c]},
        "upper": {str(c): ord(every[c].upper()) for c in range(LAST + 1)
                  if len(every[c].upper()) == 1 and every[c].upper() != every[c]},
        "casefix": casefix,
        "engine": {"not_boundary_in_empty": re.search(r"\B", "") is not None,
                   "possessive_and_atomic": sys.version_info >= (3, 11)},
    }


def merge(dumps):
    """The shipped file, from one dump per version."""
    dumps = sorted(dumps, key=lambda d: tuple(int(x) for x in d["python"].split(".")))
    newest = dumps[-1]
    classes = {}
    for name in CLASSES:
        sets = {d["python"]: points(d["classes"][name]) for d in dumps}
        common = set.intersection(*sets.values())
        classes[name] = {"common": ranges(sorted(common)),
                         "extra": {v: ranges(sorted(s - common)) for v, s in sets.items()}}
    # the characters joined to one whose case mapping differs between versions
    edges, varying = {}, set()
    for key in ("lower", "upper", "casefix"):
        tables = [d[key] for d in dumps]
        for code in set().union(*tables):
            values = [json.dumps(t.get(code)) for t in tables]
            if len(set(values)) > 1:
                varying.add(int(code))
            for t in tables:
                found = t.get(code)
                for other in (found if isinstance(found, list) else [found] if found is not None else []):
                    edges.setdefault(int(code), set()).add(other)
                    edges.setdefault(other, set()).add(int(code))
    seen, frontier = set(varying), list(varying)
    while frontier:
        for other in edges.get(frontier.pop(), ()):
            if other not in seen:
                seen.add(other)
                frontier.append(other)
    engine = {key: [d["python"] for d in dumps if d["engine"][key]] for key in newest["engine"]}
    return {"dialect": "python",
            "versions": [{"python": d["python"], "release": d["release"], "unicode": d["unicode"]}
                         for d in dumps],
            "classes": classes, "unassigned": newest["unassigned"],
            "case_varies": ranges(sorted(seen)), "engine": engine}


if __name__ == "__main__":
    if sys.argv[1] == "dump":
        Path(sys.argv[2]).write_text(json.dumps(dump()))
    else:
        merged = merge([json.loads(Path(p).read_text()) for p in sys.argv[2:]])
        DATA.write_text(json.dumps(merged, separators=(",", ":"), sort_keys=True) + "\n")
        print([v["python"] + " " + v["unicode"] for v in merged["versions"]],
              {k: {v: sum(hi - lo + 1 for lo, hi in r) for v, r in c["extra"].items()}
               for k, c in merged["classes"].items()},
              "case_varies", sum(hi - lo + 1 for lo, hi in merged["case_varies"]), merged["engine"])
