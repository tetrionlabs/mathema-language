# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A payment provider's charge events as a JSON Schema."""

CHARGE_EVENT = {
    "type": "object",
    "properties": {
        "type": {"enum": ["charge.succeeded", "charge.failed", "charge.refunded"]},
        "amount": {"type": "integer", "minimum": 0},
    },
    "required": ["type", "amount"],
    "additionalProperties": False,
}
