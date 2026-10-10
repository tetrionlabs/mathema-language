# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A purchase order as a Spark schema, in the JSON Spark writes for a
`StructType`."""
from __future__ import annotations

PURCHASE_ORDER = {
    "type": "struct",
    "fields": [
        {"name": "po_id", "type": "string", "nullable": False, "metadata": {}},
        {"name": "quantity", "type": "integer", "nullable": False, "metadata": {}},
        {"name": "unit_price", "type": "decimal(10,2)", "nullable": False, "metadata": {}},
        {"name": "po_value", "type": "decimal(18,2)", "nullable": True, "metadata": {}},
    ],
}
