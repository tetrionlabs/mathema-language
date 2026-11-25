# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Claims over the words' languages land on the verdict the function
earns, through core: a function that agrees with a word's language holds
over it (or is proven over it), and one that differs on a member of it,
a lower-case postcode, a text that ends with "ab" but does not start
with it, an accented lower-case letter, is falsified. Needs a core with
the word registry."""
import ipaddress
import re

import pytest

from mathema_language import words

pytestmark = pytest.mark.skipif(not words._WORDS, reason="this mathema has no word registry")


def postcode(s):
    return re.fullmatch(r"[A-Za-z]{2}[0-9]{2} ?[0-9][A-Za-z]{2}", s) is not None


def postcode_upper(s):
    return re.fullmatch(r"[A-Z]{2}[0-9]{2} ?[0-9][A-Z]{2}", s) is not None


def in_ten(s):
    try:
        return ipaddress.ip_address(s) in ipaddress.ip_network("10.0.0.0/8")
    except ValueError:
        return False


def in_ten_wrong(s):
    return s.startswith("10.") and "\n" not in s


def under_ws(s):
    return not s.startswith("/") or s == "/ws" or s.startswith("/ws/")


def starts_ab(s):
    return s.startswith("ab")


def has_digit(s):
    return any(c.isdigit() for c in s)


def is_lower_word(s):
    return re.fullmatch(r"[a-z]+", s) is not None


CASES = [
    (postcode, 'for s in L[ascii, pattern ("AA99[ ]9AA")], f(s) == True', "holds"),
    (postcode_upper, 'for s in L[ascii, pattern ("AA99[ ]9AA")], f(s) == True', "falsified"),
    (postcode_upper, 'for s in L[ascii, pattern ("AA99[ ]9AA", A = upper)], f(s) == True', "holds"),
    (in_ten, 'for s in L[ipv4, within ("10.0.0.0/8")], f(s) == True', "holds"),
    (in_ten_wrong, 'for s in L[ipv4, within ("10.0.0.0/8")], f(s) == True', "holds"),
    (under_ws, 'for s in L[path, within ("/ws")], f(s) == True', "holds"),
    (starts_ab, 'for s in L[ascii, ^= "ab"], f(s) == True', "holds"),
    (starts_ab, 'for s in L[ascii, $= "ab"], f(s) == True', "falsified"),
    (has_digit, 'for s in L[unicode, contains (re(r"[0-9]", python))], f(s) == True', "holds"),
    (has_digit, 'for s in L[unicode, contains (re(r"\\d", python))], f(s) == True', "holds"),
    (is_lower_word, 'for s in L[unicode, matches (re(r"[a-z]+$", python))], f(s) == True', "holds"),
    (is_lower_word, 'for s in L[unicode, matches (pattern ("a{1+}"))], f(s) == True', "falsified"),
    (is_lower_word, 'for s in L[ascii, pattern ("a{1+}")], f(s) == True', "holds"),
]


@pytest.mark.parametrize("fn, text, verdict", CASES, ids=[f"{c[0].__name__}: {c[1][8:48]}" for c in CASES])
def test_a_claim_over_a_word_s_language_lands_on_its_verdict(fn, text, verdict):
    from mathema.conjecture import check_conjectures, claim
    (found,) = check_conjectures(fn, [claim(text)])
    landed = "holds" if found.verdict == "proven" else found.verdict
    assert landed == verdict, (text, found.verdict, found.counterexample)
