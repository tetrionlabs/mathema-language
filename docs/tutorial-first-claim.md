<!-- github-only -->
> This page is part of the mathema documentation, [read it on the site](https://mathema.tetrionlabs.com/language/reference/tutorial-first-claim/).
<!-- /github-only -->

# Your first claim

<!-- shop: urls -->
<!-- requires: django -->

This page and the five after it are the tutorial. Read them in order:
each one adds one idea to the page before it, using the same small shop
throughout (its code is in `examples/shop`). The case studies, the how-to
pages and the reference can be read in any order once you have been
through them.

## A test you already have

Django's `slugify` turns a title into the part of a URL that names it.
This is its own test, from
[`tests/utils_tests/test_text.py`](https://github.com/django/django/blob/6.1.1/tests/utils_tests/test_text.py#L351-L374)
in Django 6.1.1 (BSD-3-Clause, copyright Django Software Foundation and
individual contributors):

```python title="django/tests/utils_tests/test_text.py"
    def test_slugify(self):
        items = (
            # given - expected - Unicode?
            ("Hello, World!", "hello-world", False),
            ("spam & eggs", "spam-eggs", False),
            (" multiple---dash and  space ", "multiple-dash-and-space", False),
            ("\t whitespace-in-value \n", "whitespace-in-value", False),
            ("underscore_in-value", "underscore_in-value", False),
            ("__strip__underscore-value___", "strip__underscore-value", False),
            ("--strip-dash-value---", "strip-dash-value", False),
            ("__strip-mixed-value---", "strip-mixed-value", False),
            ("_ -strip-mixed-value _-", "strip-mixed-value", False),
            ("spam & ıçüş", "spam-ıçüş", True),
            ("foo ıç bar", "foo-ıç-bar", True),
            ("    foo ıç bar", "foo-ıç-bar", True),
            ("你好", "你好", True),
            ("İstanbul", "istanbul", True),
        )
        for value, output, is_unicode in items:
            with self.subTest(value=value):
                self.assertEqual(text.slugify(value, allow_unicode=is_unicode), output)
```

It is a good test. Each row is an input someone chose and the output
they expected, and together the rows pin down what `slugify` does with
punctuation, runs of dashes, surrounding whitespace and a few scripts
other than English. What it can't say is anything about the strings
nobody wrote down.

## Your code

The shop builds each product's URL from its name:

```python
from django.utils.text import slugify


def product_slug(name: str) -> str:
    """The product's name as it appears in its URL, /products/<slug>/."""
    return slugify(name)
```

A test for it in the same style picks a name and checks the slug:

```python
assert product_slug("Blue Mug") == "blue-mug"
```

That passes, and so would any number of rows like it.

## Say what you need

What the shop needs from `product_slug` is not any particular slug but a
rule: every product gets a URL, so the slug is never empty. Not for any
name at all, since a name of punctuation alone has nothing to keep, but
for any name with at least one letter in it. As a claim:

```text
for name in L[unicode_alpha, len >= 1], len(product_slug(name)) >= 1
```

A claim reads like the sentence it replaces. `L[unicode_alpha, len >= 1]`
is every string of one or more letters, in any script; `for name in` says
the rest must hold for each of them; and the rest is the rule itself,
calling the function by its name.

Check it from the shell, the same way as any other claim:

```bash
mathema check shop/urls.py:product_slug --claim "for name in L[unicode_alpha, len >= 1], len(product_slug(name)) >= 1"
```

```text
FAIL shop.urls.product_slug: source, no side effects; claims 1/1 adjudicated (0 proven, 0 holds, 1 falsified)  <- 1 falsified claim(s)
```

The shell gives the count. The input that broke it comes from Python:

```python
import mathema
from shop.urls import product_slug

(p,) = mathema.claims.check_conjectures(
    product_slug,
    [mathema.claim("for name in L[unicode_alpha, len >= 1], len(product_slug(name)) >= 1",
                   name="every_product_has_a_url")])
print(p.verdict, p.counterexample)
```

<!-- output -->
```text
falsified name = 'а': 0 vs 1
```

## Read the failure

`falsified` means mathema ran `product_slug` on a name the claim covers
and the claim was false for it. The witness is that name, `'а'`, and
`0 vs 1` is the two sides of `>=`: the slug had length 0.

The `а` is not the Latin letter. It is the Cyrillic one, which looks the
same:

```text
name        'а'    U+0430 CYRILLIC SMALL LETTER A
ASCII form  ''     no ASCII spelling, so dropped
slug        ''     /products//
```

By default `slugify` converts to ASCII and drops whatever has no ASCII
spelling, which is all of Cyrillic, Greek, Arabic, Chinese and most of
the world's writing. Django says so in the docstring, and its test covers
those scripts with `allow_unicode=True`, the rows ending in `True`. So
Django is right and its test is right. The gap is between the fourteen
strings the test chose and every name your shop might be given, and the
claim found it because it was about every name.

mathema found it quickly because the language `unicode_alpha` offers
the letters code most often gets wrong (Japanese, Cyrillic, ligatures,
letters that change length when their case does) before random ones,
and it shrank the failing name to a single letter before reporting it.
[Reading a result](tutorial-reading-a-result.md) covers both.

## Fix it and check again

Keep every script:

```python
def product_slug_unicode(name: str) -> str:
    """The product's name as it appears in its URL, any script kept."""
    return slugify(name, allow_unicode=True)
```

```python
from shop.urls import product_slug_unicode

(p,) = mathema.claims.check_conjectures(
    product_slug_unicode,
    [mathema.claim("for name in L[unicode_alpha, len >= 1], len(product_slug_unicode(name)) >= 1",
                   name="every_product_has_a_url")])
print(p.verdict, p.n)
```

<!-- output -->
```text
holds 160
```

`holds` means mathema ran the function on 160 names from the domain,
the hard ones first, and the claim was true for every one. It is
evidence, not proof; a claim mathema can prove comes back `proven`, and
[Records](tutorial-records.md) shows one.

## Keep the claim with the code

A claim is worth more next to the function than in a shell history. Put
it in the docstring, under `Claims:`, with a name:

```python
def product_slug_unicode(name: str) -> str:
    """The product's name as it appears in its URL, any script kept.

    Claims:
        every_product_has_a_url: for name in L[unicode_alpha, len >= 1], len(product_slug_unicode(name)) >= 1
    """
    return slugify(name, allow_unicode=True)
```

and `mathema check` finds it there:

```bash
mathema check shop/urls.py:product_slug_unicode
```

```text
ok   shop.urls.product_slug_unicode: source, no side effects; claims 1/2 adjudicated (0 proven, 1 holds, 0 falsified, 1 skipped)
```

The second claim is one mathema adds to every function by itself, that
it can be called at all; it is skipped because a bare `str` parameter
says nothing about which strings it takes. Your claim is the one that
holds.

Next: [Reading a result](tutorial-reading-a-result.md).
