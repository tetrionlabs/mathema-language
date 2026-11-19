# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The hash of each of a fixed list of pattern terms, as this interpreter
builds them: for every supported Python at once, and pinned to one
version. A term must come out the same whichever supported interpreter
builds it, so the output of this script is the same under each. It loads
the term module by its path and uses the standard library only, so any
interpreter runs it bare:

    uv run --python 3.10 --no-project python tests/_python_term_hashes.py

With `write` it records the hashes in `tests/data/python_term_hashes.json`."""
import importlib.util
import json
import re
import sys
from pathlib import Path

HASHES = Path(__file__).parent / "data" / "python_term_hashes.json"
MODULE = Path(__file__).parent.parent / "src" / "mathema_language" / "text" / "_regular.py"

PATTERNS = [
    (r"a$", 0), (r"\Aa\Z", 0), (r"^[a-z0-9]+(?:-[a-z0-9]+)*$", 0), (r"\w+", 0), (r"\w+", re.A),
    (r"\d{2,4}", 0), (r"\s", 0), (r"[^\W\d]x", 0), (r"\bfoo\b", 0), (r"\B", 0), (r"\Ba", re.A),
    (r"(?i)[a-z]+k", 0), (r"(?i)\w", 0), (r"(?i)s", 0), (r"(?i)\u00df", 0), (r"(?i)[\u0100-\u2fff]", 0),
    (r"(?m)^b$", 0), (r"(?s).", 0), (r".", 0), (r"(a)\1", 0), (r"(?=a)a", 0), (r"(?a:\w)\w", 0),
    (r"[^\n]+?\s*(?:\n|$)", 0), (r"(\w+)\s*(>=|<=|>|<)\s*(-?\d+(?:\.\d+)?)", 0), (r"\U00010570", re.I),
    (r"(?:\b\w){2}", 0), (r"(?x) a b # c", 0), (r"[\d\s]", 0), (r"\D", 0), (r"a{1000}", 0),
]


def load():
    spec = importlib.util.spec_from_file_location("_regular", MODULE)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_regular"] = module
    spec.loader.exec_module(module)
    return module


def hashes():
    """Each pattern's term hash under each predicate, unpinned and pinned to 3.12."""
    rx = load()
    out = []
    for pattern, flags in PATTERNS:
        for predicate in rx.PREDICATES:
            for version in (None, "3.12"):
                doc = rx.term(pattern, flags, predicate, version=version)
                out.append({"pattern": pattern, "flags": int(flags), "predicate": predicate,
                            "python": version, "exact": doc["exact"], "hash": rx.term_hash(doc)})
    return out


if __name__ == "__main__":
    found = hashes()
    if sys.argv[1:] == ["write"]:
        HASHES.write_text(json.dumps(found, indent=0, ensure_ascii=True) + "\n")
    else:
        print(json.dumps(found, ensure_ascii=True))
