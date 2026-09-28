# Dataclasses

<!-- shop: shipping -->

The dataclass adaptor reads any class `dataclasses.is_dataclass` says
is one, and its members are instances of that class. There is no
validator in the standard library, so membership is the package's own
neutral checker, which holds each field to the type and the bounds the
annotations spell. It needs nothing installed beyond mathema and this
package, and it runs on every Python the package supports.

## What it reads

| Dataclass spelling | Neutral model | Notes |
|---|---|---|
| `int`, `float`, `bool`, `str`, `bytes`, `Decimal` | the matching base type | |
| `date`, `time`, `datetime`, `timedelta` | `date`, `time`, `datetime`, `duration` | |
| `Literal["web", "shop"]` | a categorical with those levels | |
| `list[T]`, `tuple[T, ...]`, `set[T]` | a list of `T` | |
| `dict[K, V]` | a map from `K` to `V` | |
| a nested dataclass, TypedDict or pydantic model | a struct of its fields | |
| `T \| None`, `Optional[T]` | nullable | |
| `Annotated[T, Ge(1), Le(10)]` | `min`, `max` | read by attribute, so `annotated_types`, pydantic's `Field` and any look-alike work: `gt`, `ge`, `lt`, `le`, `min_length`, `max_length`, `multiple_of` |
| a default or a `default_factory` | the field's default | |
| a `pattern` marker | refused | the standard library has nothing to hold a regular expression to, so the adaptor refuses the class and names pydantic or a JSON Schema instead |
| `__post_init__` and any other code | not read | a check written in code is invisible to the neutral model |

## A worked claim

The shop's parcels, from `examples/shop/shipping.py`:

```python
from dataclasses import dataclass
from typing import Annotated

from annotated_types import Ge, Le, MaxLen


@dataclass
class Parcel:
    postcode: Annotated[str, MaxLen(8)]
    weight_kg: Annotated[float, Ge(0.0), Le(30.0)]


def postage(parcel: Parcel) -> float:
    """What it costs to send the parcel: a base rate plus a rate per kilo."""
    return 3.5 + 1.2 * parcel.weight_kg
```

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `postage` | `for parcel in L[shop.shipping.Parcel], 3.5 <= f(parcel) <= 39.5` | proven | The lift reads the weight's bounds off the annotation, nought to thirty kilos. |
| `postage` | `for parcel in L[shop.shipping.Parcel], f(parcel) <= 30` | falsified | A thirty-kilo parcel costs 39.50. |

## A non-member

```python
from mathema_language.schema.adaptors import adapt_row

language = adapt_row(Parcel)
for problem in language.explain(Parcel(postcode="SW1A 1AAXX", weight_kg=31.0)):
    print(repr(problem.path), "|", problem.predicate)
```

<!-- output -->
```text
'.postcode' | len <= 8
'.weight_kg' | <= 30.0
```
