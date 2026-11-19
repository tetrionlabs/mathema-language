# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The recorded verdicts of a JavaScript engine on generated patterns.

`cases()` is a fixed list of (pattern, flags, texts) drawn from a grammar
of ECMAScript patterns plus hand-picked ones; `record()` runs each
through Node under the four predicates and returns the verdicts with the
Node, V8 and Unicode versions that gave them. Run as a module to write
them to `tests/data/javascript_regex_corpus.json`:

    uv run python -m tests._javascript_corpus

Each predicate is asked of a fresh sticky `RegExp` at a stated start:
`starts with` at the start of the string; `contains` at every position a
search visits (every code unit, or under `u` or `v` every code point, or
the start alone under `y`); `matches` and `ends with` likewise with the
pattern closed by `(?![\\s\\S])`, the end of the string under every flag.
The positions are stated because V8's own search under `u` also tries the
middle of a surrogate pair, which ECMA-262's does not. A pattern the
engine refuses is recorded as an error."""
import json
import random
import subprocess
from pathlib import Path

CORPUS = Path(__file__).parent / "data" / "javascript_regex_corpus.json"
NODE = "/opt/homebrew/bin/node"
PREDICATES = ("matches", "contains", "starts with", "ends with")

_DRIVER = r"""
const cases = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const out = cases.map(([pattern, flags, texts]) => {
  const sticky = flags.includes('y') ? flags : flags + 'y';
  const closed = '(?:' + pattern + ')(?![\\s\\S])';
  const byPoint = flags.includes('u') || flags.includes('v');
  const starts = t => {
    if (flags.includes('y')) return [0];
    const at = [];
    for (let i = 0; i <= t.length; i++) {
      const pair = byPoint && i > 0 && i < t.length &&
        t.charCodeAt(i - 1) >= 0xD800 && t.charCodeAt(i - 1) <= 0xDBFF &&
        t.charCodeAt(i) >= 0xDC00 && t.charCodeAt(i) <= 0xDFFF;
      if (!pair) at.push(i);
    }
    return at;
  };
  try {
    const from = (src, t, i) => { const r = new RegExp(src, sticky); r.lastIndex = i; return r.test(t); };
    const ask = (src, anywhere) => texts.map(
      t => (anywhere ? starts(t) : [0]).some(i => from(src, t, i)));
    return {pattern, flags, texts, verdicts: {
      'matches': ask(closed, false), 'contains': ask(pattern, true),
      'starts with': ask(pattern, false), 'ends with': ask(closed, true)}};
  } catch (e) {
    if (!(e instanceof SyntaxError)) throw e;
    return {pattern, flags, texts, error: true};
  }
});
process.stdout.write(JSON.stringify({
  node: process.versions.node, v8: process.versions.v8, unicode: process.versions.unicode,
  cases: out}));
"""

ALPHABET = ["a", "b", "A", "\n", "\r", " ", " ", "1", "٣", "_", "é", "É",
            "K", "k", "K", "s", "ſ", "ß", "ẞ", "-", "\U0001F600", "﻿",
            "c", "\U00010400", "\U00010428"]
ATOMS = ["a", "b", "k", "s", ".", "[ab]", "[^a]", r"\d", r"\w", r"\s", r"\W", r"\D", r"\S",
         "[a-c]", r"\n", "-", "^", "$", r"\b", r"\B", "", "[^\\n]", "(?=a)", "(?!b)", "(?<=a)",
         "(?<!b)", r"é", r"\x41", r"[\d_]", r"[^\w]", r"[k-s]", "ß", "\U0001F600",
         r"[^\s\d]", r"\t", r"[À-ÿ]"]
FLAGS = ["", "i", "m", "s", "u", "iu", "mu", "su", "y", "v", "im", "is", "imsu", "iy", "g", "iv"]
FIXED = ["a{", "{", "]", "}", r"\-", r"[\-]", "a{2,1}", r"(?<n>a)\k<n>", r"\k", r"\8", r"\07",
         r"[\b]", r"\cA", r"\c1", "[]", "[^]", "(?i:a)b", "(?-i:a)b", "(?m:^a)", "(?s:.)",
         r"(a)\1", r"\1(a)", r"\2(a)", r"\p{L}", r"[\p{L}]", r"\P{Lu}a", r"\u{1F600}",
         r"😀", r"[😀]", "\U0001F600+", "[\U0001F600]", ".", "^.$", "..",
         r"[\d-z]", r"[a-\d]", "a**", "(", ")", "(?:a|)*b", "(?:^|a)+", r"\w+@\w+", r"^\d+$",
         "^[a-z]+$", r"[\q{ab}]", "[a&&b]", "[[a-c]--[b]]", r"\x4", r"\u00", "a{2}", "a{2,}",
         "a{2,3}?", "{2}", "a|b|", "(?=a)*", "(?<=a)+", r"\ka", "[z-a]", r"\0", r"\00", r"\$",
         r"\a", r"\e", r"[\a]", "k", "s", "K", "ſ", r"\w", r"\W", r"[^\W]", r"\b",
         r"\B", "ß", "ẞ", "\U00010400", "$", "^", "a$", "(?m)a"]


def _generate(rng, depth=0):
    roll = rng.random()
    if depth > 2 or roll < 0.35:
        return rng.choice(ATOMS)
    if roll < 0.6:
        return _generate(rng, depth + 1) + _generate(rng, depth + 1)
    if roll < 0.75:
        return "(?:" + _generate(rng, depth + 1) + "|" + _generate(rng, depth + 1) + ")"
    sub = _generate(rng, depth + 1)
    return "(" + sub + ")" + rng.choice(["*", "+", "?", "{2}", "{1,3}", "{0,2}", "*?", "+?", "??"])


def _texts(rng, n):
    out = {"", "\n", "a"}
    while len(out) < n:
        out.add("".join(rng.choice(ALPHABET) for _ in range(rng.randint(1, 5))))
    return sorted(out)


def cases(seed=20261119, generated=260, texts=10):
    """The (pattern, flags, texts) the corpus records, the same on every run."""
    rng = random.Random(seed)
    out = [[pattern, flags, _texts(rng, 6)] for pattern in FIXED for flags in ("", "u", "i", "iu", "v")]
    out += [[_generate(rng), rng.choice(FLAGS), _texts(rng, texts)] for _ in range(generated)]
    return out


def record():
    """What Node says of every case."""
    done = subprocess.run([NODE, "-e", _DRIVER], input=json.dumps(cases()), capture_output=True,
                          text=True, check=True)
    return json.loads(done.stdout)


if __name__ == "__main__":
    recorded = record()
    CORPUS.write_text(json.dumps(recorded, ensure_ascii=True, indent=0, sort_keys=True) + "\n")
    asked = sum(len(c["texts"]) * len(PREDICATES) for c in recorded["cases"] if "error" not in c)
    print(f"{len(recorded['cases'])} patterns, {asked} verdicts, node {recorded['node']}, "
          f"v8 {recorded['v8']}, unicode {recorded['unicode']}")
