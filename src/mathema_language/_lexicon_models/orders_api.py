# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""An orders API with one operation, listing orders a page at a time."""
from __future__ import annotations

from ..openapi import operation

SPEC = {
    "openapi": "3.0.3",
    "info": {"title": "orders", "version": "1"},
    "paths": {"/orders": {"get": {
        "operationId": "listOrders",
        "parameters": [{"name": "limit", "in": "query",
                        "schema": {"type": "integer", "minimum": 1, "maximum": 100}}]}}},
}

list_orders = operation(SPEC, "listOrders")
