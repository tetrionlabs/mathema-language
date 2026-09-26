# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The Django shapes the row-language tests run over; settings are
configured here once, minimal and in memory."""
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


class OrderModelDj(models.Model):
    class Meta:
        app_label = "mathema_language_tests"

    qty = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    price = models.FloatField(validators=[MinValueValidator(0.0)])
    sku = models.CharField(max_length=8, blank=True)
    kind = models.CharField(max_length=4, choices=[("web", "web"), ("shop", "shop")])
    note = models.CharField(max_length=80, null=True, blank=True)


class SkuDj(models.Model):
    class Meta:
        app_label = "mathema_language_tests"

    name = models.CharField(max_length=20)


class LineDj(models.Model):
    class Meta:
        app_label = "mathema_language_tests"

    sku = models.ForeignKey(SkuDj, on_delete=models.CASCADE)
    qty = models.PositiveIntegerField()
    batch = models.SlugField(max_length=12)
