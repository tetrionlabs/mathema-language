# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Gate a pull request on its claim-level delta.

Reads the JSON `mathema review` wrote, prints a markdown summary for
the job, and exits 1 when the change made the store worse: a claim
newly falsified, a retirement row dropped (the usual trace of a merge
conflict resolved to one side), or a claim removed without a decision.
Everything else in the delta is reported and passes; debt that was
already on the base is not this change's to answer for.

With `--junit FILE` the same delta is written as a junit report, one
testcase per changed function, failed when that function blocks, which
a host that renders junit (GitLab's merge request widget) shows without
a comment or a token.

Usage: review_gate.py review.json [--junit review.xml]
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from xml.sax.saxutils import escape, quoteattr

BLOCKING = (
    ("newly_falsified", "newly falsified"),
    ("retired_dropped", "retirement row(s) dropped"),
    ("removed", "claim(s) removed"),
)


def blocking_lines(change: dict[str, Any]) -> list[str]:
    lines = [f"{name} newly falsified" for name in change["newly_falsified"]]
    lines += [f"{name} removed" for name in change["removed"]]
    lines += [f"retirement row dropped: {row}" for row in change.get("retired_dropped", [])]
    return lines


def junit(report: dict[str, Any], path: str) -> None:
    changes = report["changes"]
    failures = sum(1 for c in changes if blocking_lines(c))
    out = ['<?xml version="1.0" encoding="utf-8"?>',
           f'<testsuite name="mathema evidence" tests="{len(changes)}" '
           f'failures="{failures}">']
    for c in changes:
        out.append(f'  <testcase classname="mathema.review" name={quoteattr(c["key"])}>')
        lines = blocking_lines(c)
        if lines:
            out.append(f'    <failure message={quoteattr(lines[0])}>'
                       f'{escape(chr(10).join(lines))}</failure>')
        out.append("  </testcase>")
    out.append("</testsuite>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("review")
    ap.add_argument("--junit")
    args = ap.parse_args()
    with open(args.review, encoding="utf-8") as f:
        report = json.load(f)
    if args.junit:
        junit(report, args.junit)
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
        for line in blocking_lines(c):
            print(f"- `{c['key']}`: {line}")
    blocking = [(label, summary[key]) for key, label in BLOCKING if summary[key]]
    if blocking:
        print("\n**Blocked**: " + ", ".join(f"{n} {label}" for label, n in blocking))
        return 1
    print("\nNothing in this change blocks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
