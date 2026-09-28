# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Product reviews, as a Django model."""
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


def stars(review: Review) -> str:
    """The rating drawn as stars."""
    return "*" * review.rating
