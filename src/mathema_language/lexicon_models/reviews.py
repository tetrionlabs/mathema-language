# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Product reviews as a Django model."""
import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        INSTALLED_APPS=["django.contrib.contenttypes"],
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        USE_TZ=True,
    )
    django.setup()

from django.core.validators import MaxValueValidator, MinValueValidator  # noqa: E402
from django.db import models  # noqa: E402


class Review(models.Model):
    class Meta:
        app_label = "mathema_language_lexicon"

    body = models.CharField(max_length=2000)
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
