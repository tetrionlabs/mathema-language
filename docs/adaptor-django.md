# Django

<!-- requires: django -->
<!-- module: django_models -->

The Django adaptor reads a concrete subclass of `django.db.models.Model`,
and its members are unsaved instances of the model. What the field
definitions spell plainly is read into the neutral model and checked
there first; everything else is `full_clean`'s to decide, so a custom
validator on a field counts, and its message is the explanation. Fields
that need a database (relations, uniqueness) are excluded from
`full_clean`, since a single unsaved record has no table to be unique
in. It needs Django 4.2 or later, `pip install "mathema-language[django]"`,
with settings configured before the model is defined, and is tested at
4.2 and at the latest release.

## What it reads

| Django spelling | Neutral model | Notes |
|---|---|---|
| `IntegerField` and its small, big and positive kinds | `int` of the field's width, the positive kinds with `min` 0 | |
| `FloatField`, `DecimalField(max_digits, decimal_places)` | `float`, `decimal` with the bounds the digits allow | |
| `CharField(max_length)`, `TextField`, `EmailField`, `URLField` | `string`, `max_len` | |
| `SlugField`, `UUIDField` | `string` with the field's own pattern | |
| `BooleanField`, `DateField`, `TimeField`, `DateTimeField`, `DurationField`, `BinaryField` | the matching base type | a `DateTimeField` is UTC when `USE_TZ` is set |
| `choices` | a categorical | |
| `null=True` | nullable | |
| `blank=False` on a text field | `min_len` 1 | |
| `MinValueValidator`, `MaxValueValidator`, `MinLengthValidator`, `MaxLengthValidator` | the matching bounds | |
| `ForeignKey`, `OneToOneField` | the `<name>_id` column, an integer | whether the parent exists is a fact about tables, not part of this release |
| an `AutoField` primary key | nullable and not required | an unsaved record has none |
| any other validator | not read | decided by `full_clean` |

## A worked claim

```python
import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        INSTALLED_APPS=["django.contrib.contenttypes"],
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        USE_TZ=True,
    )
    django.setup()

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def upper_case(value):
    """Refuse a code with a lower-case letter in it."""
    if value != value.upper():
        raise ValidationError("sku must be upper case")


class Line(models.Model):
    class Meta:
        app_label = "shop"

    sku = models.CharField(max_length=8, validators=[upper_case])
    qty = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    price = models.FloatField(validators=[MinValueValidator(0.0)])


def line_total(line: Line) -> float:
    """Quantity times price."""
    return line.qty * line.price
```

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `line_total` | `for line in L[django_models.Line], f(line) >= 0` | proven | The lift reads both bounds off the validators, a quantity of at least one times a price of at least zero. |
| `line_total` | `for line in L[django_models.Line], f(line) <= 100` | falsified | The price has no upper bound. |

## A non-member

The first record breaks a bound the neutral model read; the second
passes it and is refused by `full_clean`, on the validator the neutral
model could not read.

```python
from mathema_language.schema.adaptors import adapt_row

language = adapt_row(Line)
for bad in (Line(sku="ABC", qty=0, price=2.5), Line(sku="abc", qty=1, price=2.5)):
    for problem in language.explain(bad):
        print(repr(problem.path), "|", problem.predicate)
```

<!-- output -->
```text
'.qty' | >= 1
'.sku' | sku must be upper case
```
