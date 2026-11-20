# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The characters of a Python identifier on each supported Python, as
data.

`str.isidentifier` accepts one character it takes first and then any
number it takes after the first, and both sets follow the interpreter's
Unicode version. `dump` records the two sets for the interpreter
running it; `merge` joins the dumps of every supported version into the
file the package ships: for each set the code points every version
holds and what each version adds. It uses the standard library only, so
any interpreter runs it bare:

    for v in 3.10 3.11 3.12 3.13 3.14; do
        uv run --python $v --no-project python tests/_python_identifier_data.py dump /tmp/$v.json
    done
    uv run python tests/_python_identifier_data.py merge /tmp/3.1*.json
"""
import json
import sys
from pathlib import Path

DATA = (Path(__file__).parent.parent / "src" / "mathema_language" / "text" / "data"
        / "python_identifier_characters.json")
LAST = 0x10FFFF

SETS = {
    "start": str.isidentifier,
    "continue": lambda c: ("a" + c).isidentifier(),
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
    return {"python": f"{sys.version_info[0]}.{sys.version_info[1]}",
            "sets": {name: ranges([c for c in range(LAST + 1) if inside(chr(c))])
                     for name, inside in SETS.items()}}


def merge(dumps):
    """The shipped file, from one dump per version."""
    dumps = sorted(dumps, key=lambda d: tuple(int(x) for x in d["python"].split(".")))
    out = {"versions": [d["python"] for d in dumps], "sets": {}}
    for name in SETS:
        sets = {d["python"]: points(d["sets"][name]) for d in dumps}
        common = set.intersection(*sets.values())
        out["sets"][name] = {"common": ranges(sorted(common)),
                             "extra": {v: ranges(sorted(s - common)) for v, s in sets.items()}}
    return out


if __name__ == "__main__":
    if sys.argv[1] == "dump":
        Path(sys.argv[2]).write_text(json.dumps(dump()))
    else:
        merged = merge([json.loads(Path(p).read_text()) for p in sys.argv[2:]])
        DATA.write_text(json.dumps(merged, separators=(",", ":"), sort_keys=True) + "\n")
        print(merged["versions"], {name: {v: sum(hi - lo + 1 for lo, hi in r)
                                          for v, r in entry["extra"].items()}
                                   for name, entry in merged["sets"].items()})
