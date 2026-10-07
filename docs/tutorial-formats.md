<!-- github-only -->
> This page is part of the mathema documentation, [read it on the site](https://mathema.tetrionlabs.com/language/reference/tutorial-formats/).
<!-- /github-only -->

# Formats

<!-- shop: formats -->
<!-- requires-python: 3.11 -->

Most strings an application handles are not free text but a format: an
order id, a date, a token. Code that takes a format does three things
with it, and each has a claim: it refuses what isn't in the format, it
normalises what is, and whatever it writes, it can read back.

## A format is a language too

`L[uuid]` is every string `uuid.UUID` accepts, `L[iso_date]` every
string `date.fromisoformat` accepts on the Python you are running, and
[Languages](languages.md) lists the rest (`L[ipv4]`, `L[base64]`,
`L[hex]`, `L[slug]` and more). Each is defined by the parser Python
already has, so a claim over one means the same thing that parser does.

## Refusing what isn't in the format

The shop reads an order id out of the URL. This function and the others
on this page are in `shop/formats.py`:

```python
def parse_order_id(text: str) -> uuid.UUID:
    """The order id in a URL, or a ValueError when it is not one."""
    return uuid.UUID(text)
```

The docstring promises a `ValueError` for anything else, which is what
the web framework turns into a 404. mathema has a built-in claim for
exactly that promise:

```text
f = parse_order_id
for text in L[uuid], excluded_outside_domain(text)
    holds
```

A built-in claim is about the function being checked rather than one it
names, so the line above it says which function that is. `f = ...` is
only how these pages write it down: in practice the function is the one
you check, `mathema check shop/formats.py:parse_order_id --claim "for text in L[uuid], excluded_outside_domain(text)"`,
or the one whose docstring the claim sits in.
`excluded_outside_domain(text)` says every string outside the domain is
refused, where refused means the function raises `ValueError`. mathema
tries the strings just outside the format (a UUID with a letter out of
range, one character short, the empty string) along with the usual
troublemakers, and the claim fails if any of them is accepted or raises
anything else, since a `TypeError` from deep inside a parser is a 500,
not a 404.

## Normalising, once

The database keeps order ids in one spelling:

```python
def normalise_order_id(text: str) -> str:
    """The order id as the database stores it."""
    return str(uuid.UUID(text))
```

It is tempting to assume the id in the URL already is that spelling:

```text
for text in L[uuid], normalise_order_id(text) == text
    falsified   text = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa': 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa' vs 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
```

`uuid.UUID` reads an id without hyphens, and in capitals, and in
braces, so a lookup that compares the URL's text with the stored text
will miss orders that exist. What does hold is that normalising twice
changes nothing, which is the property a normaliser exists to have:

```text
for text in L[uuid], normalise_order_id(normalise_order_id(text)) == normalise_order_id(text)
    holds
```

Dates catch people the same way:

```python
def normalise_date(text: str) -> str:
    """A delivery date as the shop stores it."""
    return dt.date.fromisoformat(text).isoformat()
```

```text
for text in L[iso_date], normalise_date(text) == text
    falsified   text = '00060908': '0006-09-08' vs '00060908'
```

```text
text     '00060908'     ISO 8601's basic format: year 0006, month 09, day 08
stored   '0006-09-08'   the extended format, with hyphens
```

`20260928` is as much an ISO date as `2026-09-28`, and so is the week
date `2026-W39-1`; `date.fromisoformat` reads all three from Python
3.11 on. The shrunk witness has an odd year only because smaller
numbers are simpler; any basic-format date fails the same way.

## Round trips

The payment gateway hands the shop an API token, which the shop decodes
and passes on encoded again:

```python
def reencode_token(token: str) -> str:
    """An API token as the gateway passes it on."""
    return base64.b64encode(base64.b64decode(token)).decode("ascii")
```

Decoding and encoding again should give back what came in, character
for character, or the gateway will refuse a token it issued:

```text
for token in L[base64], reencode_token(token) == token
    holds
```

This is a round trip, and it is worth a claim whenever data leaves in
one form and comes back in another: encode and decode, serialise and
parse, write and read. The claim is short, and it covers every value
of the format rather than the three a test would pick.

Next: [Records](tutorial-records.md).
