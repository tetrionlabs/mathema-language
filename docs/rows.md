# Rows

A schema is a language too. `L[myapp.models.Order]` names the records of
a dataclass, a TypedDict, a pydantic model, a JSON Schema, a SQLAlchemy
table or a Django model, read into one neutral model by an adaptor and
validated by the library's own validator where it has one (pydantic's,
the JSON Schema validator, an in-memory SQLite database for SQLAlchemy,
`full_clean` for Django). A parameter annotated with the class infers
the language on its own:

```
for o in L[myapp.models.Order], f(o) >= 0
```

The probe visits one record per field hazard first (the extremes, the
text corpus in a string column, the longest string a column allows, the
datetime64[ns] bounds and a DST edge), and a witness names the field in
one path grammar for every ecosystem, `.qty` for a column and
`.ship.city` for a nested one.

A row can be proven, not only sampled. Where the body reads only numeric
fields, and text fields only through `len`, the derive route lifts each
field the body reads to a symbol bounded by the schema, a quantity
annotated `Ge(1), Le(10)` as a whole number from one to ten, a price
annotated `Ge(0.0)` as a real at least zero, `len(o.sku)` on a field
annotated `MaxLen(8)` as a whole number from nought to eight, so
`for o in L[Order], f(o) >= 0` over `o.qty * o.price` is proven, and the
fields the body never reads (a note, a list of tags) do not stand in the
way. Where the body reads a field the lift has no reading of, a
`Literal` compared against a string, say, the lift declines, the note
names the field, and the claim is sampled instead.

The adaptors that read a schema, in the order they are asked, and how
to write one of your own, are on [writing an adaptor](adaptors.md).
