<!-- github-only -->
> This page is part of the mathema documentation, [read it on the site](https://mathema.tetrionlabs.com/language/reference/adaptor-typeddict/).
<!-- /github-only -->

# TypedDicts

<!-- shop: search -->

The TypedDict adaptor reads any class `typing.is_typeddict` says is
one, and its members are plain dicts. Like the dataclass adaptor it has
no validator to borrow, so membership is the neutral checker: every
required key present, every value of its type and inside its bounds. It
needs nothing installed beyond mathema and this package.

## What it reads

| TypedDict spelling | Neutral model | Notes |
|---|---|---|
| a key's type hint | as for a dataclass field | the same hint reader, so the same types, markers and nesting |
| `total=False`, `NotRequired[T]` | the key is not required | a missing optional key is a member |
| `Required[T]` | the key is required | |
| `Annotated[T, ...]` markers | the matching constraints | read by attribute, as for a dataclass |
| a key the TypedDict does not name | refused | the neutral model reads a TypedDict's keys as the whole record |

## A worked claim

A search result as the shop's search service returns it, from
`examples/shop/search.py`:

```python
from typing import Annotated, TypedDict

from annotated_types import Ge, Le


class SearchHit(TypedDict):
    title: str
    score: Annotated[float, Ge(0.0), Le(1.0)]
    clicks: Annotated[int, Ge(0)]


def rank(hit: SearchHit) -> float:
    """Where the hit sorts: relevance first, popularity after."""
    return hit["score"] * 10 + hit["clicks"] / 1000
```

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `rank` | `for hit in L[shop.search.SearchHit], f(hit) >= 0` | proven | The lift reads both keys' bounds off the annotations, through the subscripts the body uses. |
| `rank` | `for hit in L[shop.search.SearchHit], f(hit) <= 10` | falsified | Nothing bounds the clicks from above. |

## Enforcing the schema

A function that guards a boundary should refuse a record its schema
rejects. `excluded_outside_domain` feeds it records just outside the
language, and the witness names the value and why it is outside, in
the library's own words. This function trusts its input, so a record
the schema rejects goes straight through:

```python
def result_title(hit: SearchHit) -> str:
    """The title shown for a result."""
    return hit["title"]
```

```text
f = result_title
for hit in L[shop.search.SearchHit], excluded_outside_domain(hit)
    falsified   hit = {'title': '', 'score': '1', 'clicks': 0} (outside L[shop.search.SearchHit] at .score: float)
```

The same claim over the function that loads the record, from a request
or a database, is the one that should hold.
