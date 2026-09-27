# pydantic

<!-- requires: pydantic -->
<!-- module: pydantic_models -->

The pydantic adaptor reads any subclass of `pydantic.BaseModel`, and its
members are instances of the model. Membership is the model's own
`model_validate`, so a validator you wrote on the model counts, and a
non-member is explained in pydantic's own words. The adaptor decides
whether an object is a model without importing pydantic: if pydantic
was never imported, nothing can be a model. It needs pydantic 2.0 or
later, `pip install "mathema-language[pydantic]"`, and is tested at
2.0 and at the latest release.

## What it reads

| pydantic spelling | Neutral model | Notes |
|---|---|---|
| a field's annotation | as for a dataclass field | read off `model_fields` |
| `Field(ge=1, le=10)`, `Field(gt=..., lt=...)` | `min`, `max`, `exclusive_min`, `exclusive_max` | from the field's metadata |
| `Field(min_length=..., max_length=...)` | `min_len`, `max_len` | |
| `Field(pattern=...)` | `regex` | generation draws matching strings; the model decides membership |
| `Field(multiple_of=...)` | `multiple_of` | |
| a default | the field's default, the field not required | a `default_factory` is not called at adaptation |
| `model_config = ConfigDict(extra="forbid")` | the exact column policy | an extra field is then a non-member |
| `@field_validator`, `@model_validator` | not read | enforced by `model_validate`, so generation may draw a record the model refuses, and the refusal filters it out |

## A worked claim

```python
from pydantic import BaseModel, ConfigDict, Field


class Line(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str = Field(max_length=8)
    qty: int = Field(ge=1, le=10)
    price: float = Field(ge=0.0)


def line_total(line: Line) -> float:
    """Quantity times price."""
    return line.qty * line.price
```

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `line_total` | `for line in L[pydantic_models.Line], f(line) >= 0` | proven | The lift reads both bounds off the model's fields, a quantity of at least one times a price of at least zero. |
| `line_total` | `for line in L[pydantic_models.Line], f(line) <= 100` | falsified | The price has no upper bound. |

## A non-member

```python
from mathema_language.schema.adaptors import adapt_row

language = adapt_row(Line)
bad = Line.model_construct(sku="ABCDEFGHIJ", qty=0, price=2.5)
for problem in language.explain(bad):
    print(repr(problem.path), "|", problem.predicate)
```

<!-- output -->
```text
'.sku' | String should have at most 8 characters
'.qty' | Input should be greater than or equal to 1
```
