<!-- github-only -->
> This page is part of the mathema documentation, [read it on the site](https://mathema.tetrionlabs.com/language/reference/tutorial-first-claim/).
<!-- /github-only -->

# Your first claim

<!-- shop: urls -->
<!-- requires: django -->

This page and the five after it are the tutorial. Read them in order:
each one adds one idea to the page before it, using the same small shop
throughout. The case studies, the how-to pages and the reference can be
read in any order once you have been through them.

## Where things go

The shop is an ordinary Python package, in `examples/shop` in this
repository, with a module for each part of the application:

```text
examples/
└── shop/
    ├── urls.py       product URLs
    ├── text.py       usernames and display text
    ├── formats.py    order ids, dates, tokens
    ├── forms.py      pydantic forms: signup, cart, checkout
    ├── db.py         SQLAlchemy tables: orders
    └── threads.py    comment threads
```

Functions live in these modules, and so do the records they take (a
pydantic model, a SQLAlchemy table, a dataclass), the same as in any
application. Nothing about them changes for mathema.

Claims are separate. A claim names the function it is about, so it does
not have to sit in the same file, and there are three places to put one:

- on the command line, `mathema check shop/urls.py:product_slug --claim "..."`,
  for one you are trying out;
- in a short Python script that calls `mathema.claims.check_conjectures`,
  when you want the whole result, the failing input included;
- next to the code, to keep it: in the function's docstring under
  `Claims:`, or in a claims file such as `claims/urls.claims.yaml`.

This page uses all three, in that order. To follow along, install
mathema and Django in a virtual environment (`pip install "mathema[all]" django`)
and run every command from `examples/`, so that `shop/urls.py` is a path
and `shop.urls` is a module Python can import.

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

The shop builds each product's URL from its name, in `shop/urls.py`:

```python
from django.utils.text import slugify


def product_slug(name: str) -> str:
    """The product's name as it appears in its URL, /products/<slug>/."""
    return slugify(name)
```

A test for it in the same style, in the shop's test suite, picks a name
and checks the slug:

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

Nothing has been written to a file yet. The quickest way to check a
claim is to pass it on the command line, from `examples/`:

```bash
mathema check shop/urls.py:product_slug --claim "for name in L[unicode_alpha, len >= 1], len(product_slug(name)) >= 1"
```

```text
FAIL shop.urls.product_slug: source, no side effects; claims 1/1 checked (0 proven, 0 holds, 1 falsified)  <- 1 falsified claim(s)
```

The shell gives the count but not the input that broke it. For that,
ask from Python. Save this as `check_slug.py` in `examples/`, beside the
`shop` folder, and run `python check_slug.py`:

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

`check_conjectures` takes the function and a list of claims, and returns
one result for each, `p` here, whose `verdict` and `counterexample` are
the two things printed.

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

The fix keeps every script. Add it to `shop/urls.py`, under the first
version:

```python
def product_slug_unicode(name: str) -> str:
    """The product's name as it appears in its URL, any script kept."""
    return slugify(name, allow_unicode=True)
```

and add the same claim, now about the new function, to the end of
`check_slug.py`:

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

So far the claim has lived in a shell command and a throwaway script,
and the next person to change `product_slug_unicode` won't see either.
A claim is worth more next to the function. The simplest place is the
function's own docstring in `shop/urls.py`, under `Claims:`, with a
name:

```python
def product_slug_unicode(name: str) -> str:
    """The product's name as it appears in its URL, any script kept.

    Claims:
        every_product_has_a_url: for name in L[unicode_alpha, len >= 1], len(product_slug_unicode(name)) >= 1
    """
    return slugify(name, allow_unicode=True)
```

`mathema check` reads it from there, so the command no longer needs
`--claim`:

```bash
mathema check shop/urls.py:product_slug_unicode
```

```text
ok   shop.urls.product_slug_unicode: source, no side effects; claims 1/1 checked (0 proven, 1 holds, 0 falsified)
```

If you'd rather keep claims out of the source (because the module
belongs to someone else, or because a reviewer should see them in one
place), put them in a claims file instead. mathema finds any file named
`*.claims.yaml` under the directory you run it from, keyed by the
function's dotted name. As `examples/claims/urls.claims.yaml`:

```yaml
shop.urls.product_slug:
  claims:
    - name: every_product_has_a_url
      statement: "for name in L[unicode_alpha, len >= 1], len(product_slug(name)) >= 1"
```

and `mathema check shop/urls.py:product_slug`, with no `--claim`, picks
it up and reports the same falsified claim as before. The two places
can be mixed; where both name the same claim, the file wins.

Next: [Reading a result](tutorial-reading-a-result.md).
