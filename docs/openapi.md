<!-- github-only -->
> This page is part of the mathema documentation, [read it on the site](https://mathema.tetrionlabs.com/language/reference/openapi/).
<!-- /github-only -->

# OpenAPI operations

<!-- module: openapi_page -->
<!-- requires: jsonschema -->

An OpenAPI 3 specification already says exactly what each operation
accepts, so each operation is a language: the requests it accepts. A
request is a record of the operation's parameters by where they arrive,
`path`, `query`, `headers` and `cookies`, and its JSON `body`, each
parameter typed as its schema types it, so a query parameter declared
as an integer is an int rather than the text it arrived as.

```python
from mathema_language.openapi import operation

spec = {
    "openapi": "3.0.3",
    "info": {"title": "orders", "version": "1"},
    "paths": {
        "/orders": {
            "get": {"operationId": "listOrders",
                    "parameters": [{"name": "limit", "in": "query",
                                    "schema": {"type": "integer", "minimum": 1, "maximum": 100}}]},
            "post": {"operationId": "createOrder",
                     "requestBody": {"required": True, "content": {"application/json": {"schema": {
                         "type": "object", "required": ["sku", "quantity"],
                         "properties": {"sku": {"type": "string", "minLength": 1},
                                        "quantity": {"type": "integer", "minimum": 1}}}}}}}},
        "/orders/{id}": {
            "delete": {"operationId": "cancelOrder",
                       "parameters": [{"name": "id", "in": "path", "required": True,
                                       "schema": {"type": "integer", "minimum": 1}}]}},
    },
}
```

`operation(spec, "createOrder").language` is a record language like any
JSON Schema one: it draws requests, checks them with `jsonschema`, and is
what a claim about the operation ranges over.

```python
create = operation(spec, "createOrder")
print(create.language.contains({"body": {"sku": "ABC-1", "quantity": 3}}))
print(create.language.contains({"body": {"sku": "ABC-1", "quantity": 0}}))
```

<!-- output -->
```text
True
False
```

Each operation also says what its HTTP method promises, as the method's
own semantics define it: a GET reads only, a PUT or DELETE is
idempotent, and a DELETE destroys.

```python
for op_id in ("listOrders", "createOrder", "cancelOrder"):
    op = operation(spec, op_id)
    print(op.method, op.path, op.read_only, op.idempotent, op.destructive)
```

<!-- output -->
```text
get /orders True True False
post /orders False False False
delete /orders/{id} False True True
```

## Naming an operation in a claim

A claim names an operation by the dotted path of a module attribute that
holds one, the way it names a model class:

```text
# app/api.py
create_order = operation(SPEC, "createOrder")

# a claim over the requests it accepts
for req in L[app.api.create_order], quantity_of(req) >= 1
```

## What it reads

A path parameter is always required, a query, header or cookie
parameter when it says so, and the body when `requestBody.required` is
true. References inside the specification (`#/components/...`) are
inlined, and a schema that refers to itself is refused by name. OpenAPI
3.0's `nullable: true` is a type that also admits null. The body must be
JSON. How a value is spelt on the wire (`style`, `explode`,
percent-encoding) is not read: the language is of requests once their
parameters are parsed.

Because the request is a JSON Schema record, mathema's z3 encoding reads
it, nested parameters and body included, so whether a new version of an
operation accepts every request the old one did is a question with a
proof or a request that breaks, as for any two record schemas.
