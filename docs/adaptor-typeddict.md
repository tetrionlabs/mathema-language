# TypedDicts

<!-- module: typeddict_models -->

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

```python
from typing import Annotated, TypedDict

from annotated_types import Ge, Le, MaxLen


class Line(TypedDict):
    sku: Annotated[str, MaxLen(8)]
    qty: Annotated[int, Ge(1), Le(10)]
    price: Annotated[float, Ge(0.0)]


def line_total(line: Line) -> float:
    """Quantity times price."""
    return line["qty"] * line["price"]
```

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `line_total` | `for line in L[typeddict_models.Line], f(line) >= 0` | holds | Sampled, not proven: the lift does not yet read a field through a subscript, so the probe decides it over valid records, hazards first. |
| `line_total` | `for line in L[typeddict_models.Line], f(line) <= 100` | falsified | The price has no upper bound. |

## A non-member

```python
from mathema_language.schema.adaptors import adapt_row

language = adapt_row(Line)
for problem in language.explain({"sku": "ABC", "qty": 11, "note": "x"}):
    print(repr(problem.path), "|", problem.predicate)
```

<!-- output -->
```text
'.qty' | <= 10
'.price' | present
'.note' | a column of the schema
```
