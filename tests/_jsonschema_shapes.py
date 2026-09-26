# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The JSON Schema shape the row-language tests run over."""
ORDER_SCHEMA = {
    "title": "OrderSchema",
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "qty": {"type": "integer", "minimum": 1, "maximum": 10},
        "price": {"type": "number", "minimum": 0},
        "sku": {"type": "string", "maxLength": 8},
        "kind": {"enum": ["web", "shop"]},
        "note": {"type": ["string", "null"], "default": None},
    },
    "required": ["id", "qty", "price", "sku", "kind"],
    "additionalProperties": False,
}
