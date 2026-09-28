# mathema-language

**mathema for strings, records and schemas.**

mathema checks claims about code, proving them where it can and
falsifying them with a real input where they are wrong, and every claim
quantifies over a domain. For a function of numbers that domain is `R`
or `[0, 1]`. This package supplies the domains for what most application
code actually takes: strings (`L[unicode]`, `L[json]`, `L[slug]`),
records (a pydantic model, a dataclass, a TypedDict), and the schemas
that already describe them (a SQLAlchemy table, a Django model, a JSON
Schema), all written the same way, `L[...]`.

```
pip install mathema-language
```

mathema finds the package through its entry points once installed, so
there is nothing to configure. Without it, mathema still parses and
records an `L[...]` domain but resolves no name, and a claim over one is
skipped with the reason.

Every example below is real code from a small shop in
[`examples/shop`](examples/shop), and every verdict is the one the test
suite gets when it runs the claim.

## Strings

A username shown upper-cased in a header whose column holds 32
characters, and a value put in an HTTP header:

```text
f = display_name
for username in L[unicode, len <= 32], len(f(username)) <= 32
    falsified   ('aﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁ'): 33 vs 32

f = header_value
for value in L[latin-1], f(value) == value
    falsified   ('\xa0'): raised UnicodeEncodeError

for value in L[ascii], f(value) == value
    holds
```

Upper-casing looks as though it keeps a string's length, and over the
whole of Unicode it does not: the ligature `ﬁ` upper-cases to the two
letters `FI`, so a 17-character name overflows the column. A probe
drawing random letters would almost never try it and would report
`holds` for a claim that is false. Every language here visits its
hazards first, the strings real code mishandles, collected from what
the test suites of Django, Werkzeug, MarkupSafe, ftfy and CPython found
the hard way, and a length bound fills the characters that grow up to
the bound, so this is among the first inputs tried rather than a lucky
draw. The header is the same lesson at an alphabet boundary: encoding as
ASCII fails on the no-break space, which is latin-1 but not ASCII, and
over `L[ascii]` it holds.

With `in` and `not in`, a claim holds an output to a language or keeps
a token out of it:

```text
f = slugify
for title in L[unicode], f(title) in L[slug]
    falsified   (''): '' is not in L[slug]

f = render_comment
for body in L[unicode], "<" not in f(body)
    holds

f = normalise_config
for text in L[json], f(f(text)) == f(text)
    holds
```

A title with no ASCII letter or digit in it slugifies to the empty
string, which is not a slug, so the post gets no URL. Each language is
decided by Python's own reading of it, never a regular expression
standing in for a parser:

| Name | Members | Membership |
|---|---|---|
| `unicode` | every `str`, lone surrogates included | none needed |
| `ascii`, `latin-1` | strings over those code points | `ord(c) < 128`, `< 256` |
| `printable` | what Python calls printable | `str.isprintable` |
| `digit` | strings over the ten ASCII digits | `c in "0123456789"` |
| `alpha`, `alnum` | letters, and letters with digits, any script | `str.isalpha`, `str.isalnum` |
| `identifier` | Python identifiers | `str.isidentifier` |
| `json` | what Python's JSON parser accepts | `json.loads` |
| `uuid` | every spelling `uuid.UUID` reads | `uuid.UUID` |
| `iso_date`, `iso_datetime` | ISO 8601 dates and times | `fromisoformat` |
| `ipv4`, `ipv6` | addresses | `ipaddress` |
| `base64`, `hex` | encoded bytes | `b64decode(validate=True)`, `bytes.fromhex` |
| `slug` | lower-case words joined by single hyphens | `[a-z0-9]+(-[a-z0-9]+)*` |
| `shell_safe` | a word a shell reads literally | `shlex.quote(s) == s` |

An alphabet language includes the empty string, and `L[ascii] \ {""}`
leaves it out. The characters parsers tend to get wrong are languages
of their own, so a claim can quantify over exactly them: `c0`,
`format`, `combining`, `surrogate`, `nfkc_folding` and `non_bmp`.

## Records and schemas

Whatever already describes a record is a language, and names its
records: `L[shop.db.Order]` is every row the orders table accepts,
`L[shop.forms.SignupForm]` every form pydantic validates. A parameter
annotated with the class infers its language on its own.

```python
class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(sa.String(12), sa.CheckConstraint("length(sku) >= 3"))
    quantity: Mapped[int] = mapped_column(sa.CheckConstraint("quantity BETWEEN 1 AND 100"))
    unit_price: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2),
                                                sa.CheckConstraint("unit_price >= 0"))


def order_total(order: Order) -> Decimal:
    return order.quantity * order.unit_price


class SignupForm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=32)
    age: int = Field(ge=13, le=120)


def years_until_adult(form: SignupForm) -> int:
    return max(0, 18 - form.age)
```

```text
f = order_total
for order in L[shop.db.Order], f(order) >= 0
    proven

f = years_until_adult
for form in L[shop.forms.SignupForm], 0 <= f(form) <= 5
    proven
```

Both are proven, not sampled: the fields a function reads become symbols
bounded by the schema (the table's CHECK constraints, the model's
`Field` bounds) and the ordinary prover runs. Where a function reads a
field the proof has no reading of, it says which, and the claim is
sampled instead.

A JSON Schema is a language of the documents it validates, which is
how a webhook handler meets every event the provider can send, including
the one the router forgot:

```text
f = queue_for
for event in L[shop.webhooks.CHARGE_EVENT], f(event) in {"billing", "alerts"}
    falsified   ({'type': 'charge.refunded', 'amount': 0}): raised KeyError
```

A binding reaches into a record at any depth, through fields and
indices, and `[*]` means every element. The witness is shrunk at every
level, so it keeps only what the failure needs:

```text
f = largest_quantity
for cart in L[shop.forms.Cart], f(cart) <= 3
    falsified   (Cart(items=[CartItem(sku='', quantity=4)])): 4 vs 3

for cart in L[shop.forms.Cart], cart.items[*].quantity in [1, 3], f(cart) <= 3
    holds
```

## Trees

A record that refers to itself is a language of trees: a comment and
its replies, a folder and its contents, a category and its
subcategories.

```python
@dataclass
class Comment:
    author: str
    body: str
    replies: list[Comment] = field(default_factory=list)


def thread_size(comment: Comment) -> int:
    return 1 + sum(thread_size(r) for r in comment.replies)
```

```text
f = thread_size
for comment in L[shop.threads.Comment, depth <= 50], f(comment) >= 1
    proven

for comment in L[shop.threads.Comment], f(comment) >= 1
    falsified   (<Comment nested 2100 levels deep (1050 Comment records)>): raised RecursionError
```

The first is proven by structural induction: true for a comment with no
replies, and true for a comment whenever it is true of each reply. The
second is the same function on a thread of any depth, and there the
mathematics is still right while the code is not: a reply chain a
thousand deep exhausts Python's recursion, and the probe builds one.
`depth`, `nodes` and `children` bound a tree inside the brackets,
counted in records, and the hazards visit the deepest and widest trees
the bounds allow and the ones just past them.

## Adaptors

An adaptor reads one library's schema objects into the package's
neutral model. Where the library has its own validator, that validator
decides membership, so a record is valid exactly when your code's own
library says so.

| Adaptor | Reads | Membership decided by |
|---|---|---|
| pydantic | a `BaseModel` subclass, with `Field` bounds and constraints | `model_validate` |
| SQLAlchemy | a mapped class or a `Table`, with types, `nullable` and CHECK constraints | inserting the row into in-memory SQLite |
| Django | a `Model` subclass, with field types, options and validators | `full_clean` |
| JSON Schema | a schema as a dict, local `$ref` included | the `jsonschema` validator |
| dataclass | a dataclass, with `Annotated` bounds | the package's own checker |
| TypedDict | a `TypedDict`, with `Annotated` bounds | the package's own checker |
| text | a `str` parameter, and `Annotated[str, MaxLen(n)]` | the text languages |

The library ones are optional extras (`pip install
"mathema-language[pydantic]"`, `[sqlalchemy]`, `[django]`,
`[jsonschema]`, or `[all]`), and an adaptor never imports its library
unless the object in front of it came from that library. Adaptors are
ordinary registrations under mathema's `mathema.language_adaptors`
entry-point group, so one for another library is written and found the
same way: [writing an adaptor](docs/adaptors.md) describes the contract
and the conformance checks a new one's tests can call.

## Where next

- [What to claim](docs/catalogue.md): the claims worth writing for a
  parser, renderer, normaliser, validator, escaper or consumer, each
  with a real function and the verdict the test suite holds it to.
- [Rows](docs/rows.md), [recursive structures](docs/recursive.md), and a
  page for each adaptor in [the reference](docs/index.md).
- Your own language: any object satisfying
  `mathema.languages.Language`, registered with `register_language`,
  under a `mathema.languages` entry point, or named by its dotted path,
  `L[myapp.text.SKU]`.

## Requirements

Python 3.10 or later and mathema 0.6.1 or later. The package imports
only from `mathema.interfaces.extension`, the surface mathema versions
for extension authors, and a test pins that.

## Licence

Apache-2.0. mathema itself is licensed separately.
