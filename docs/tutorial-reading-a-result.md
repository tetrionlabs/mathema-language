# Reading a result

<!-- shop: urls -->
<!-- requires: django -->

Every claim comes back with a verdict, and most come back with more:
how the verdict was reached, and when the claim fails, the input that
broke it. This page reads all of it, on the `product_slug_unicode` from
[the first page](tutorial-first-claim.md).

The pages from here on write a claim and its result together, the claim
on one line and what mathema reported indented beneath it:

```text
for name in L[unicode], product_slug_unicode(product_slug_unicode(name)) == product_slug_unicode(name)
    holds
```

This one says slugifying a slug changes nothing, which is what lets a
URL built from a slug be slugified again safely, and it holds.

## Three verdicts

A claim over a handful of names you choose yourself:

```text
for name in {"Blue Mug", "Чай", "Café au lait"}, len(product_slug_unicode(name)) >= 1
    proven
```

`proven` means the claim is true for every member of the domain, not
just the ones tried. Here the domain has three members, so mathema
called the function on all three, and the record says so:

```python
import mathema
from shop.urls import product_slug_unicode

(p,) = mathema.claims.check_conjectures(
    product_slug_unicode,
    [mathema.claim('for name in {"Blue Mug", "Чай", "Café au lait"}, '
                   'len(product_slug_unicode(name)) >= 1', name="three_names")])
print(p.verdict)
print(p.condition)
```

<!-- output -->
```text
proven
∀ name in the declared finite domain (3 points)
```

Over `L[unicode]` there is no visiting every member, and nothing in
mathema reads what a function does to a string symbolically, so a claim
about every string comes back `holds` at best:

```python
(p,) = mathema.claims.check_conjectures(
    product_slug_unicode,
    [mathema.claim("for name in L[unicode], product_slug_unicode(product_slug_unicode(name)) "
                   "== product_slug_unicode(name)", name="idempotent")])
print(p.verdict, p.n)
print(p.meta["mathema.sampling"])
```

<!-- output -->
```text
holds 224
name~L[unicode], seed=20260718, n=224
```

`holds` means mathema called the function on 224 names and the claim was
true for every one. The sampling line says how they were drawn, and with
the same seed a second run draws the same names, so a `holds` is
repeatable rather than lucky. It is evidence, not proof, and mathema
never reports one as the other. (A claim over records can come back
`proven` while its domain is still infinite, because mathema can reason
about a record's fields; [Records](tutorial-records.md) shows it.)

The third verdict is the one worth having:

```text
for name in L[unicode, len <= 50], len(product_slug_unicode(name)) <= 50
    falsified   name='0℀…': 51 vs 50
```

Django's `SlugField` holds 50 characters unless told otherwise, and a
product name capped at 50 characters sounds as if it should fit.

## Reading a witness

A witness has two parts either side of the colon. Before it, each
argument the claim reads, by name; after it, what went wrong. For a
comparison that is the two sides, left then right: the slug was 51
characters and the claim allowed 50.

```text
name   '0℀℀℀…℀'     26 code points: '0', then 25 of U+2100 ACCOUNT OF
slug   '0acac…ac'   51 characters, since NFKC turns each ℀ into a/c
                    and slugify drops the slash
```

A column declared for 50 characters won't take that slug: PostgreSQL
refuses the insert, and SQLite stores it anyway. Other claims fail in
other words: a membership claim says `'::.0' is not in L[ipv6]`, and a
function that raised says `raised UnicodeEncodeError`.

## The inputs tried first

mathema found `℀` because a language brings its own list of the inputs
code most often gets wrong, and those are tried before random ones. A
few of the list for `L[unicode]`:

```python
from mathema_language.text import UNICODE

for hazard in UNICODE.hazards():
    if hazard.value in ("\u200b", "\ud800", "ﬁ", "İ", "℀", "²", "nan"):
        print(f"{hazard.value!r:10} {hazard.note}")
```

<!-- output -->
```text
'\u200b'   a zero-width space
'\ud800'   a lone surrogate, which no codec can encode
'℀'        account of, which NFKC folds to a/c
'ﬁ'        the fi ligature, one code point that upper-cases to two
'İ'        capital I with a dot, one code point that lower-cases to two
'nan'      text that spells not-a-number
'²'        superscript two, a digit str.isdigit accepts and int refuses
```

Each is a real way text breaks code, and none of them is the sort of
string a hand-written test tends to include.

## Shrinking

The first name that breaks a claim is rarely the clearest one. Before
reporting it, mathema tries smaller members of the same domain, keeping
each that still fails, until none does:

```python
(p,) = mathema.claims.check_conjectures(
    product_slug_unicode,
    [mathema.claim("for name in L[unicode, len <= 50], len(product_slug_unicode(name)) <= 50",
                   name="fits_the_column")])
print(p.meta["mathema.witness_shrunk"])
```

<!-- output -->
```text
{'steps': 21}
```

Twenty-one steps took it to the smallest name that still overflows:
twenty-five `℀` make exactly 50 characters of slug, and the `0` is the
one character more.

## When there is no verdict

Two more words can come back. `skipped` means mathema couldn't run the
claim at all, for instance because it names a function mathema can't
find, and `unknown` means it ran but could not decide. Either way the
note (`p.note`) says why.

Next: [Choosing the inputs](tutorial-choosing-inputs.md).
