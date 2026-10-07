<!-- github-only -->
> This page is part of the mathema documentation, [read it on the site](https://mathema.tetrionlabs.com/language/reference/adaptor-jsonschema/).
<!-- /github-only -->

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
4.22 or later, `pip install "mathema-language[jsonschema]"`, and is
tested at 4.22 and at the latest release.

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

## Enforcing the schema

A function that guards a boundary should refuse a record its schema
rejects. `excluded_outside_domain` feeds it records just outside the
language, and the witness names the value and why it is outside, in
the library's own words. This function trusts its input, so a record
the schema rejects goes straight through:

```text
f = queue_for
for event in L[shop.webhooks.CHARGE_EVENT], excluded_outside_domain(event)
    falsified   event = {'type': 'charge.succeeded', 'amount': None} (outside L[shop.webhooks.CHARGE_EVENT] at .amount: None is not of type 'integer')
```

The same claim over the function that loads the record, from a request
or a database, is the one that should hold.
