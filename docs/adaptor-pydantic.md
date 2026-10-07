<!-- github-only -->
> This page is part of the mathema documentation, [read it on the site](https://mathema.tetrionlabs.com/language/reference/adaptor-pydantic/).
<!-- /github-only -->

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


def years_until_eighteen(form: SignupForm) -> int:
    """How many years until the user turns 18."""
    return max(0, 18 - form.age)
```

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `years_until_eighteen` | `for form in L[shop.forms.SignupForm], 0 <= f(form) <= 5` | proven | The lift reads the age's bounds off the model's fields, so the wait is between none and five years. |
| `years_until_eighteen` | `for form in L[shop.forms.SignupForm], f(form) <= 4` | falsified | A thirteen-year-old waits five years. |

## Enforcing the schema

A function that guards a boundary should refuse a record its schema
rejects. `excluded_outside_domain` feeds it records just outside the
language, and the witness names the value and why it is outside, in
the library's own words. This function trusts its input, so a record
the schema rejects goes straight through:

```python
def welcome_message(form: SignupForm) -> str:
    """The first line of the welcome email."""
    return f"Welcome, {form.username}!"
```

```text
f = welcome_message
for form in L[shop.forms.SignupForm], excluded_outside_domain(form)
    falsified   form = SignupForm(username='aaa', age=12) (outside L[shop.forms.SignupForm] at .age: Input should be greater than or equal to 13)
```

The same claim over the function that loads the record, from a request
or a database, is the one that should hold.
