# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Purchase orders as the procurement pipeline reads them, with the
schema the pipeline passes to `spark.read.schema(...)`."""
from decimal import Decimal

PURCHASE_ORDER = {
    "type": "struct",
    "fields": [
        {"name": "po_id", "type": "string", "nullable": False, "metadata": {}},
        {"name": "quantity", "type": "integer", "nullable": False, "metadata": {}},
        {"name": "unit_price", "type": "decimal(10,2)", "nullable": False, "metadata": {}},
        {"name": "po_value", "type": "decimal(18,2)", "nullable": True, "metadata": {}},
    ],
}


def spend_band(po: dict) -> str:
    """The spend band a purchase order is reported under."""
    value = po["po_value"]
    if value is None or value < 0:
        return "Invalid"
    if value < 1000:
        return "Micro"
    if value < 10000:
        return "Standard"
    if value < 50000:
        return "Strategic"
    return "Major"


def line_total(po: dict) -> Decimal:
    """What the order's lines come to."""
    return po["quantity"] * po["unit_price"]
