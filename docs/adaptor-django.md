# Django

<!-- requires: django -->
<!-- shop: reviews -->

The Django adaptor reads a concrete subclass of `django.db.models.Model`,
and its members are unsaved instances of the model. What the field
definitions spell plainly is read into the neutral model and checked
there first; everything else is left to `full_clean`, so a custom
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

The shop's product reviews, from `examples/shop/reviews.py`:

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

from django.core.exceptions import ValidationError  # noqa: E402
from django.core.validators import MaxValueValidator, MinValueValidator  # noqa: E402
from django.db import models  # noqa: E402


def no_links(value):
    """Refuse a review body with a link in it."""
    if "http://" in value or "https://" in value:
        raise ValidationError("links are not allowed in a review")


class Review(models.Model):
    class Meta:
        app_label = "shop"

    body = models.CharField(max_length=2000, validators=[no_links])
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])


def weight(review: Review) -> float:
    """How much the review counts toward the product's score."""
    return review.rating / 5
```

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `weight` | `for review in L[shop.reviews.Review], 0 < f(review) <= 1` | proven | The lift reads the rating's bounds off the validators, one to five stars. |
| `weight` | `for review in L[shop.reviews.Review], f(review) >= 0.5` | falsified | A one-star review counts for a fifth. |

## A non-member

The first review breaks a bound the neutral model read; the second
passes it and is refused by `full_clean`, on the validator the neutral
model could not read.

```python
from mathema_language.schema.adaptors import adapt_row

language = adapt_row(Review)
for bad in (Review(body="great", rating=6), Review(body="see https://example.com", rating=4)):
    for problem in language.explain(bad):
        print(repr(problem.path), "|", problem.predicate)
```

<!-- output -->
```text
'.rating' | <= 5
'.body' | links are not allowed in a review
```
