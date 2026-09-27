# JSON Schema

<!-- requires: jsonschema -->
<!-- module: jsonschema_models -->

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

```python
LINE = {
    "title": "Line",
    "type": "object",
    "properties": {
        "sku": {"type": "string", "maxLength": 8},
        "qty": {"type": "integer", "minimum": 1, "maximum": 10},
        "price": {"type": "number", "minimum": 0},
    },
    "required": ["sku", "qty", "price"],
    "additionalProperties": False,
}


def line_total(line: dict) -> float:
    """Quantity times price."""
    return line["qty"] * line["price"]
```

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `line_total` | `for line in L[jsonschema_models.LINE], f(line) >= 0` | holds | Sampled, not proven: the lift does not yet read a field through a subscript. |
| `line_total` | `for line in L[jsonschema_models.LINE], f(line) <= 100` | falsified | The price has no upper bound. |

## A non-member

```python
from mathema_language.schema.adaptors import adapt_row

language = adapt_row(LINE)
for problem in language.explain({"sku": "ABCDEFGHIJ", "qty": 0, "price": 2.5, "note": "x"}):
    print(repr(problem.path), "|", problem.predicate)
```

<!-- output -->
```text
'.sku' | 'ABCDEFGHIJ' is too long
'.qty' | 0 is less than the minimum of 1
'' | Additional properties are not allowed ('note' was unexpected)
```
