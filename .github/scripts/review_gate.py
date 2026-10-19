# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Gate a pull request on its claim-level delta.

Reads the JSON `mathema review` wrote, prints a markdown summary for
the job, and exits 1 when the change made the store worse: a claim
newly falsified, a retirement row dropped (the usual trace of a merge
conflict resolved to one side), or a claim removed without a decision.
Everything else in the delta is reported and passes; debt that was
already on the base is not this change's to answer for.

Usage: review_gate.py review.json
"""
from __future__ import annotations

import json
import sys

BLOCKING = (
    ("newly_falsified", "newly falsified"),
    ("retired_dropped", "retirement row(s) dropped"),
    ("removed", "claim(s) removed"),
)


def main(path: str) -> int:
    with open(path, encoding="utf-8") as f:
        report = json.load(f)
    summary = report["summary"]
    changes = report["changes"]
    print(f"### mathema evidence (against `{report['base']}`)\n")
    if not changes:
        print("No claim changed.\n")
        return 0
    print("| function | added | removed | flipped | newly falsified |")
    print("|:---|---:|---:|---:|---:|")
    for c in changes:
        print(f"| `{c['key']}` | {len(c['added'])} | {len(c['removed'])} "
              f"| {len(c['flipped'])} | {len(c['newly_falsified'])} |")
    print()
    for c in changes:
        for name in c["newly_falsified"]:
            print(f"- `{c['key']}`: **{name}** newly falsified")
        for name in c["removed"]:
            print(f"- `{c['key']}`: `{name}` removed")
        for row in c.get("retired_dropped", []):
            print(f"- `{c['key']}`: retirement row dropped: `{row}`")
    blocking = [(label, summary[key]) for key, label in BLOCKING if summary[key]]
    if blocking:
        print("\n**Blocked**: " + ", ".join(f"{n} {label}" for label, n in blocking))
        return 1
    print("\nNothing in this change blocks.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
