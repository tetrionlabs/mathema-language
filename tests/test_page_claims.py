# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A page states a claim either after an `f = name` line or by naming
the function in the claim itself; either way the check runs against the
function the claim is about."""
from tests._shop_pages import blocks, claim_blocks, claimed_function

_NAMED = """
```text
for name in L[unicode_alpha, len >= 1], len(product_slug(name)) >= 1
    falsified   name = 'а': 0 vs 1
```
"""

_AFTER_F = """
```text
f = display_name
for username in L[unicode, len <= 32], len(f(username)) <= 32
    falsified   username = 'aﬁ…': 33 vs 32
```
"""


def product_slug(name):
    return name


def product_slug_unicode(name):
    return name


def test_a_claim_block_reads_the_claim_its_verdict_and_witness():
    ((fn, law, verdict, witness),) = claim_blocks(_NAMED)
    assert fn is None
    assert law.startswith("for name in")
    assert (verdict, witness) == ("falsified", "name = 'а': 0 vs 1")


def test_a_claim_naming_its_function_is_about_that_function_after_an_f_line():
    scope = {"product_slug": product_slug, "display_name": len}
    ((fn, law, *_),) = claim_blocks(_NAMED)
    assert claimed_function(law, scope, "display_name") is product_slug


def test_a_built_in_claim_is_about_the_f_line_s_function():
    scope = {"product_slug": product_slug}
    assert claimed_function("for s in L[unicode], is_encoding_safe(s)", scope,
                            "product_slug") is product_slug


def test_the_claimed_function_is_the_first_one_called_that_the_page_defines():
    scope = {"product_slug": product_slug, "product_slug_unicode": product_slug_unicode}
    law = "for name in L[unicode], product_slug_unicode(product_slug_unicode(name)) == product_slug_unicode(name)"
    assert claimed_function(law, scope) is product_slug_unicode
    assert claimed_function("for name in L[unicode], len(product_slug(name)) >= 1", scope) is product_slug


def test_a_titled_block_is_quoted_code_and_is_neither_run_nor_compared():
    page = '```python title="tests/utils_tests/test_text.py"\n    def test_slugify(self):\n        pass\n```\n'
    assert blocks(page) == []


def test_a_claim_opening_with_let_is_read():
    page = """
```text
f = username_key
let nfkc = mathema_language.text.nfkc, for name in L[unicode], f(nfkc(name)) == f(name)
    falsified   name = '℀': 'a/c' vs '℀'
```
"""
    ((fn, law, verdict, witness),) = claim_blocks(page)
    assert fn == "username_key" and law.startswith("let nfkc")
    assert (verdict, witness) == ("falsified", "name = '℀': 'a/c' vs '℀'")
