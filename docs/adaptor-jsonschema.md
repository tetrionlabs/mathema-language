# JSON Schema

<!-- requires: jsonschema -->
<!-- shop: webhooks -->

The JSON Schema adaptor reads a dict with `"type": "object"` and a
`"properties"` mapping, and its members are dicts. Membership is the
`jsonschema` package's validator for the schema's own draft, and the
explanation path is the validator's `absolute_path`, so a nested field
reads `.ship.city`. Deciding whether a dict is a schema needs no
import; validating one does, so a schema with `jsonschema` not
installed is refused with the extra to install. It needs `jsonschema`
4.18 or later, `pip install "mathema-language[jsonschema]"`, and is
tested at 4.18 and at the latest release.

## What it reads

| JSON Schema keyword | Neutral model | Notes |
|---|---|---|
| `type` (`integer`, `number`, `string`, `boolean`, `array`, `object`) | the matching base type | a list of types with `"null"` is nullable |
| `required` | the named fields are required | |
| `additionalProperties: false` | the exact column policy | |
| `minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum` | the matching bounds | |
| `minLength`, `maxLength`, `minItems`, `maxItems` | `min_len`, `max_len` | |
| `pattern` | `regex` | |
| `enum`, `const`, `multipleOf`, `default` | the matching constraint | an `enum` with no `type` is a categorical |
| `anyOf`, `oneOf` with a `"null"` branch | nullable | other unions read as `any` |
| a nested `object` | a struct | |
| `$ref` | refused | inline the definition |
| `format` | not read | the validator decides it when a format checker is configured |

## A worked claim

The payment provider's charge events and the shop's router, from
`examples/shop/webhooks.py`:

```python
CHARGE_EVENT = {
    "type": "object",
    "properties": {
        "type": {"enum": ["charge.succeeded", "charge.failed", "charge.refunded"]},
        "amount": {"type": "integer", "minimum": 0},
    },
    "required": ["type", "amount"],
    "additionalProperties": False,
}

QUEUES = {"charge.succeeded": "billing", "charge.failed": "alerts"}


def queue_for(event: dict) -> str:
    """The queue a charge event is routed to."""
    return QUEUES[event["type"]]


def processing_fee(event: dict) -> float:
    """The provider's fee on a charge, in cents: 2.9% plus 30."""
    return event["amount"] * 0.029 + 30
```

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `processing_fee` | `for event in L[shop.webhooks.CHARGE_EVENT], f(event) >= 30` | proven | The lift reads the amount's minimum off the schema. |
| `queue_for` | `for event in L[shop.webhooks.CHARGE_EVENT], f(event) in {"billing", "alerts"}` | falsified | A `charge.refunded` event has no queue, and the router raises KeyError. |

## A non-member

```python
from mathema_language.schema.adaptors import adapt_row

language = adapt_row(CHARGE_EVENT)
for problem in language.explain({"type": "charge.disputed", "amount": -5, "note": "x"}):
    print(repr(problem.path), "|", problem.predicate)
```

<!-- output -->
```text
'.type' | 'charge.disputed' is not one of ['charge.succeeded', 'charge.failed', 'charge.refunded']
'.amount' | -5 is less than the minimum of 0
'' | Additional properties are not allowed ('note' was unexpected)
```
