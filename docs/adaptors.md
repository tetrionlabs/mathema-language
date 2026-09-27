# Writing an adaptor

<!-- module: my_adaptor -->

An adaptor turns one library's schema object into a language whose
members are that library's records, and there will be many of them, so
the package's own seven have no privileged path: each is an ordinary
registration under mathema's `mathema.language_adaptors` entry-point
group, found through the same registry an adaptor from your package is
found through, and held to the same conformance harness. The pages
beside this one describe the seven: [dataclasses](adaptor-dataclass.md),
[TypedDicts](adaptor-typeddict.md), [pydantic](adaptor-pydantic.md),
[JSON Schema](adaptor-jsonschema.md), [SQLAlchemy](adaptor-sqlalchemy.md),
[Django](adaptor-django.md) and [text annotations](adaptor-text.md).

## The contract

An adaptor is a callable, `adapt(obj)`, that answers a language for a
schema object of its own library and `None` for anything else, and it
decides "not mine" without importing its library: if the library was
never imported, nothing in the process can be one of its objects, so
`sys.modules.get("mylib")` is the whole test. It may refuse an object
that is its own but that it cannot read faithfully (a `$ref` it does
not follow, a regular expression with no validator to hold it to) by
raising with a message that says what to do instead.

## Which adaptor is asked first

mathema asks the adaptors in an explicit order: an adaptor may carry
`__mathema_adaptor_priority__`, an int, and a higher one is asked first,
ties going to the entry-point name. The package uses three bands, and an
adaptor from another package should use the same ones:

| Priority | For | Here |
|---|---|---|
| 100 | an adaptor that recognises a library's own model classes | pydantic, SQLAlchemy, Django |
| 50 | a schema written as data | JSON Schema |
| 0 | a structural reading of any class of a standard shape, or of a plain annotation | dataclass, TypedDict, text |

So a class two adaptors would both accept goes to the more specific
one: a SQLAlchemy class that is also a dataclass (`MappedAsDataclass`)
is read by the SQLAlchemy adaptor, with its database constraints, rather
than by the dataclass adaptor, which would see only the annotations.

## The public surface

What an adaptor needs is in `mathema_language.schema`: the neutral model
(`RowSchema`, `Field`, `NeutralType`, `Constraints`, `BASES`,
`NO_DEFAULT`), the `Ecosystem` protocol (`name`, `accepts`, `to_model`,
`build_row`, `validate_row`), two ecosystems to reuse (`PlainEcosystem`
for records as dicts, `AttributeEcosystem` for records as instances of
a class), and `RowLanguage(schema, ecosystem, name)`, which does the
rest: generation per field, the hazards, `outside`, shrinking, and the
field bounds the derive lift reads. A library with a validator of its
own writes an ecosystem whose `validate_row` calls it, so membership is
the library's, the way the pydantic ecosystem calls `model_validate`.

## An example

A small library that describes a record as a class with a `SPEC`
mapping of field names to types:

```python
import sys

from mathema_language.schema import (Constraints, Field, NeutralType,
                                     AttributeEcosystem, RowLanguage, RowSchema)


class Spec:
    """The base class of the imaginary library's records."""


class Line(Spec):
    SPEC = {"qty": (int, 1, 10), "price": (float, 0.0, None)}

    def __init__(self, qty, price):
        self.qty, self.price = qty, price

    def __repr__(self):
        return f"Line(qty={self.qty!r}, price={self.price!r})"


_BASES = {int: "int", float: "float", str: "string"}


def adapt(obj):
    """The row language of a `Spec` subclass, or None."""
    base = getattr(sys.modules.get(__name__), "Spec", None)
    if base is None or not (isinstance(obj, type) and issubclass(obj, base) and obj is not base):
        return None
    fields = tuple(Field(name, NeutralType(_BASES[kind]), constraints=Constraints(min=lo, max=hi))
                   for name, (kind, lo, hi) in obj.SPEC.items())
    return RowLanguage(RowSchema(obj.__name__, fields), AttributeEcosystem(obj), obj.__name__)


adapt.__mathema_adaptor_priority__ = 100
```

It registers in the library's own `pyproject.toml`:

```toml
[project.entry-points."mathema.language_adaptors"]
speclib = "speclib.mathema:adapt"
```

## Testing it

`mathema_language.conformance` is the harness the package's own
adaptors pass. `row_adaptor_problems(obj)` lists every way the language
of `obj` falls short (empty when it conforms): the registry answers it
with this adaptor, the language satisfies mathema's protocol, every
hazard and fifty random members are members by the ecosystem's own
validator, `outside` never draws a member and explains itself in the
path grammar, every shrink stays inside, and `fields()` has the shape
the derive lift reads. `not_mine_problems(adapt)` checks the other half:
`None` for objects that are not the library's, with nothing imported
while answering. `assert_row_adaptor(obj)` is the first as an assertion.
In the library's own tests, with the adaptor installed, leave the
registry check on; here the adaptor is not installed, so it is off:

```python
from mathema_language.conformance import not_mine_problems, row_adaptor_problems

print(row_adaptor_problems(Line, adapt=adapt, registered=False))
print(not_mine_problems(adapt))
```

<!-- output -->
```text
[]
[]
```
