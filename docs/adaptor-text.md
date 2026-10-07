<!-- github-only -->
> This page is part of the mathema documentation, [read it on the site](https://mathema.tetrionlabs.com/language/reference/adaptor-text/).
<!-- /github-only -->

# Text annotations

<!-- shop: text -->

The text adaptor reads two annotations, `str` and `Annotated[str,
...]`, and nothing else. `str` is the language of every string,
`L[unicode]`; an `Annotated[str, ...]` carrying a length marker
(`MaxLen(80)`, pydantic's `max_length`, and the `min_length` side) is
that language refined by the marker, `L[unicode, len <= 80]`, and one
with no length marker is `L[unicode]`. It is how a `str` parameter with
no binding gets a language: the claim needs no `for s in ...`, and the
record's note says the language was inferred and from where. It needs
nothing installed beyond mathema and this package.

## What it reads

| Annotation | Language | Notes |
|---|---|---|
| `str` | `L[unicode]` | |
| `Annotated[str, MaxLen(80)]` | `L[unicode, len <= 80]` | the markers are read by attribute, `max_length` and `min_length` |
| `str \| None`, `Optional[str]` | not answered | how a missing value is admitted is decided in mathema itself |
| anything else | not answered | |

## A worked claim

Two of the shop's text helpers, from `examples/shop/text.py`:

```python
from typing import Annotated

from annotated_types import MaxLen


def display_name(username: str) -> str:
    """The username as shown in the header, upper-cased."""
    return username.upper()


def short_title(title: Annotated[str, MaxLen(60)]) -> str:
    """The title, cut to the sixty characters the column holds."""
    return title[:60]
```

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `display_name` | `len(f(username)) == len(username)` | falsified | Inferred `L[unicode]`, and `'ﬁ'` upper-cases to two code points. |
| `short_title` | `f(title) == title` | holds | Inferred `L[unicode, len <= 60]`, inside which the cut changes nothing. |

## Enforcing the schema

A function that guards a boundary should refuse a record its schema
rejects. `excluded_outside_domain` feeds it records just outside the
language, and the witness names the value and why it is outside, in
the library's own words. This function trusts its input, so a record
the schema rejects goes straight through:

```python
def display_name(username: str) -> str:
    """The username as shown in the header, upper-cased."""
    return username.upper()
```

```text
f = display_name
for username in L[ascii], excluded_outside_domain(username)
    falsified   username = '\ufeff' (outside L[ascii] at [0]: ascii alphabet)
```

The same claim over the function that loads the record, from a request
or a database, is the one that should hold.
