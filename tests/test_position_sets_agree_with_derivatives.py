# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The two readings `holds` switches between, position sets and
derivatives, agree on every expression the term algebra builds,
complements and intersections included, on short texts over a small
alphabet. Seeded."""
import random

from mathema_language.text import _algebra as A

_SETS = [((97, 97),), ((98, 98),), ((97, 98),), ((99, 99),)]


def _expression(rng, depth=0):
    if depth > 3 or rng.random() < 0.3:
        return rng.choice([A._chars_re(rng.choice(_SETS)), A._EPS, A._EMPTY_RE])
    kind = rng.choice(["cat", "alt", "loop", "loop", "inter", "not"])
    if kind == "cat":
        return A._cat(_expression(rng, depth + 1), _expression(rng, depth + 1))
    if kind == "alt":
        return A._alt(_expression(rng, depth + 1), _expression(rng, depth + 1))
    if kind == "inter":
        return A._inter(_expression(rng, depth + 1), _expression(rng, depth + 1))
    if kind == "not":
        return ("not", _expression(rng, depth + 1))
    lo = rng.randint(0, 3)
    hi = rng.choice([None, lo, lo + 1, lo + 3, 70, 100])
    return A._loop(_expression(rng, depth + 1), lo, None if hi is None else max(hi, lo, 1))


def _by_derivatives(r, text):
    for c in text:
        r = A._derivative(r, ord(c))
        if r == A._EMPTY_RE:
            return False
    return A._nullable(r)


def test_position_sets_and_derivatives_agree():
    rng = random.Random(1)
    for _ in range(1500):
        r = _expression(rng)
        for _ in range(20):
            text = "".join(rng.choice("abc") for _ in range(rng.randint(0, 9)))
            by_positions = len(text) in A._ends_from(r, 0, [ord(c) for c in text], {})
            assert by_positions == _by_derivatives(r, text), (r, text)
