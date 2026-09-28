# pydantic

<!-- requires: pydantic -->
<!-- shop: forms -->

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

The shop's signup form, from `examples/shop/forms.py`:

```python
from pydantic import BaseModel, ConfigDict, Field


class SignupForm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=32)
    age: int = Field(ge=13, le=120)


def years_until_adult(form: SignupForm) -> int:
    """How long until the user may see adult content."""
    return max(0, 18 - form.age)
```

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `years_until_adult` | `for form in L[shop.forms.SignupForm], 0 <= f(form) <= 5` | proven | The lift reads the age's bounds off the model's fields, so the wait is between none and five years. |
| `years_until_adult` | `for form in L[shop.forms.SignupForm], f(form) <= 4` | falsified | A thirteen-year-old waits five years. |

## A non-member

```python
from mathema_language.schema.adaptors import adapt_row

language = adapt_row(SignupForm)
bad = SignupForm.model_construct(username="ab", age=12)
for problem in language.explain(bad):
    print(repr(problem.path), "|", problem.predicate)
```

<!-- output -->
```text
'.username' | String should have at least 3 characters
'.age' | Input should be greater than or equal to 13
```
