# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Write the pull request comment for the measure job.

Takes the badges this run wrote, the base's badges when the
mathema-badges branch has them, and the coverage summary, and prints
one markdown comment: the three scores base against head, the triangle
as text, and how exact the implementation number is. When the coverage
report was restored from main rather than regenerated here, the
implementation score is a lower bound, since lines in a file that
changed since that run count only once the tests run on it again; the
comment names those files and the label that runs them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from typing import Any

MARKER = "<!-- mathema-measure -->"
SCORES = ("implementation", "intent", "clarity", "overall")


def badge_message(directory: str, score: str) -> str | None:
    path = os.path.join(directory, f"{score}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        message = json.load(f).get("message")
    return None if message is None else str(message)


def snapshot(directory: str) -> dict[str, Any]:
    path = os.path.join(directory, "snapshot.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        loaded: dict[str, Any] = json.load(f)
    return loaded


def score_text(directory: str, score: str) -> str:
    message = badge_message(directory, score)
    if message is not None:
        return message
    value = snapshot(directory).get(score)
    return "n/a" if value is None else str(value)


def changed_since_report(stamp_path: str) -> list[str]:
    """Files whose content no longer matches the coverage stamp."""
    if not os.path.exists(stamp_path):
        return []
    with open(stamp_path, encoding="utf-8") as f:
        stamp = json.load(f)
    changed = []
    for rel, digest in sorted(stamp.get("files", {}).items()):
        if not os.path.exists(rel):
            changed.append(rel)
            continue
        with open(rel, "rb") as f:
            if hashlib.sha256(f.read()).hexdigest() != digest:
                changed.append(rel)
    return changed


def potential(coverage_text: str) -> str | None:
    m = re.search(r"up to (\d+)% after re-running", coverage_text)
    return m.group(1) if m else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--head", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--base-sha", default="")
    ap.add_argument("--exact", default="false")
    ap.add_argument("--coverage", default="coverage.txt")
    ap.add_argument("--stamp", default="coverage.sources.json")
    ap.add_argument("--run-url", default="")
    args = ap.parse_args()

    exact = args.exact.lower() == "true"
    head = snapshot(args.head)
    coverage_text = ""
    if os.path.exists(args.coverage):
        with open(args.coverage, encoding="utf-8") as f:
            coverage_text = f.read()
    changed = [] if exact else changed_since_report(args.stamp)
    have_report = os.path.exists(args.stamp)

    print(MARKER)
    print("### mathema measure\n")
    base_label = f"base (`{args.base_sha[:7]}`)" if args.base_sha else "base"
    print(f"| score | {base_label} | head |")
    print("|:---|---:|---:|")
    for score in SCORES:
        head_text = score_text(args.head, score)
        if score == "implementation" and not exact and changed:
            head_text = f"at least {head_text}"
        print(f"| {score} | {score_text(args.base, score)} | {head_text} |")
    print()

    if exact:
        print("Implementation is exact: the tests ran under coverage on this commit.")
    elif not have_report:
        print("Implementation counts probes and proofs only: no coverage report "
              "was available to restore. Add the `coverage` label to run the "
              "tests under coverage here.")
    elif changed:
        up_to = potential(coverage_text)
        more = f" Up to {up_to}% counts" if up_to else " More may count"
        files = ", ".join(f"`{p}`" for p in changed[:8])
        if len(changed) > 8:
            files += f" and {len(changed) - 8} more"
        print(f"Implementation is a lower bound: the tests last ran under coverage "
              f"on main, and {len(changed)} measured file(s) changed since "
              f"({files}).{more} once the tests run on them; add the "
              f"`coverage` label to run them here.")
    else:
        print("Implementation is exact: no measured file changed since the tests "
              "ran under coverage on main.")

    capped = head.get("capped") or []
    if capped:
        # each entry names the function and the steps that stopped
        names = ", ".join(f"`{c[0]}` ({', '.join(c[1])})" if isinstance(c, list) else f"`{c}`"
                          for c in capped[:6])
        if len(capped) > 6:
            names += f" and {len(capped) - 6} more"
        print(f"\n{len(capped)} function(s) hit a wall-clock cap while being scored "
              f"and count only what finished: {names}.")

    triangle = os.path.join(args.head, "triangle.txt")
    if os.path.exists(triangle):
        with open(triangle, encoding="utf-8") as f:
            print("\n<details><summary>triangle</summary>\n\n```\n" + f.read().rstrip()
                  + "\n```\n\n</details>")
    if args.run_url:
        print(f"\nThe badge files from this run are an artifact of [the run]({args.run_url}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
