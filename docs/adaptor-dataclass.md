# Dataclasses

<!-- module: dataclass_models -->

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

```python
from dataclasses import dataclass
from typing import Annotated

from annotated_types import Ge, Le, MaxLen


@dataclass
class Line:
    sku: Annotated[str, MaxLen(8)]
    qty: Annotated[int, Ge(1), Le(10)]
    price: Annotated[float, Ge(0.0)]


def line_total(line: Line) -> float:
    """Quantity times price."""
    return line.qty * line.price
```

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `line_total` | `for line in L[dataclass_models.Line], f(line) >= 0` | proven | The lift reads both bounds off the annotations, a quantity of at least one times a price of at least zero. |
| `line_total` | `for line in L[dataclass_models.Line], f(line) <= 100` | falsified | The price has no upper bound, and an executed record is the witness. |

## A non-member

```python
from mathema_language.schema.adaptors import adapt_row

language = adapt_row(Line)
for problem in language.explain(Line(sku="ABCDEFGHIJ", qty=0, price=2.5)):
    print(repr(problem.path), "|", problem.predicate)
```

<!-- output -->
```text
'.sku' | len <= 8
'.qty' | >= 1
```
