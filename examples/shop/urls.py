# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The shop's URLs."""
from django.utils.text import slugify


def product_slug(name: str) -> str:
    """The product's name as it appears in its URL, /products/<slug>/."""
    return slugify(name)


def product_slug_unicode(name: str) -> str:
    """The product's name as it appears in its URL, any script kept.

    Claims:
        every_product_has_a_url: for name in L[unicode_alpha, len >= 1], len(product_slug_unicode(name)) >= 1
    """
    return slugify(name, allow_unicode=True)
