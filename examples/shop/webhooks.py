# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The payment provider's charge events, as a JSON Schema, and the
router that sends each to a queue."""

CHARGE_EVENT = {
    "type": "object",
    "properties": {
        "type": {"enum": ["charge.succeeded", "charge.failed", "charge.refunded"]},
        "amount": {"type": "integer", "minimum": 0},
    },
    "required": ["type", "amount"],
}

QUEUES = {"charge.succeeded": "billing", "charge.failed": "alerts"}


def queue_for(event: dict) -> str:
    """The queue a charge event is routed to."""
    return QUEUES[event["type"]]
