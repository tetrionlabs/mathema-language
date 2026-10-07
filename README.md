# mathema-language

**mathema for strings, records and schemas.**

An example-based test checks the inputs whoever wrote it thought of,
which is a good way to pin down behaviour you already understand. The
inputs that break code in production tend to be the ones nobody wrote
down: a ligature that grows when it is upper-cased, a webhook event the
router never expected, a comment thread nested deeper than Python will
recurse. mathema states a claim about every input a function takes and
either proves it or finds an input that breaks it. Until now that meant
numbers (`for x in [0, 1]`), while most application code takes strings
and records. This package supplies those domains, written `L[...]`: a
language of strings such as `L[unicode]` or `L[json]`, or the records a
schema you already have describes, such as `L[myapp.models.Order]`.

```
pip install "mathema[all]"
```

That installs mathema with this package and the schema libraries it
reads, and `pip install mathema-language` adds it to a mathema you
already have. mathema finds the package through its entry points, so
there is nothing to configure, and without it a claim over `L[...]`
comes back `unknown` with the reason "needs mathema-language".

Every example below is real code from a small shop in
[`examples/shop`](examples/shop), and every verdict is the one the test
suite gets when it runs the claim.

## What can be proven, and why

mathema proves a claim by reading a function's code as mathematics, so
what it can prove depends on how much it can reason about the input.
The three kinds of data here differ a good deal in that.

A record carries its own bounds. A pydantic model, a SQLAlchemy table
or a Django model already states what each field may hold (an age
between 13 and 120, a quantity of at least 1, a price of at least 0).
When a function reads those fields, mathema turns each one into a
symbol bounded by those constraints and proves the claim with the same
algebra it uses for numbers. The proof covers every record the schema
allows, not just the few a test would build.

A tree, a record holding records of its own kind, is proven by
structural induction, the way you would by hand: the claim holds for a
comment with no replies, and it holds for any comment whenever it holds
for each reply. That needs the recursion to finish, so the proof is over
trees of bounded depth. Over trees of any depth the claim runs into
Python's recursion limit instead, which a test that builds a
three-comment thread never shows.

Text is where proof mostly gives way to checking, because nothing reads
what an arbitrary function does to a string symbolically. A claim over
a finite set of strings is proven by trying every member, as long as
mathema can show the function is pure. A claim over a whole language is
checked: each language tries the strings code most often gets wrong
before any random ones, and shrinks a failure to the smallest input
that still shows it. So `holds` over a string language means the claim
survived those inputs, and `falsified` comes with the exact string.

## Strings

The shop shows a username upper-cased in a header 32 characters wide,
and usernames are at most 32 characters:

```python
def display_name(username: str) -> str:
    return username.upper()
```

```text
for username in L[unicode, len <= 32], len(display_name(username)) <= 32
    falsified   username = 'aﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁ': 33 vs 32
```

Upper-casing keeps a string's length for English text and doesn't over
the whole of Unicode, since the ligature `ﬁ` upper-cases to the two
letters `FI`, so a 17-character name overflows the box. A string drawn
at random would almost never be made of ligatures, so the language puts
the characters whose case changes their length near the front of what
it tries.

An alphabet's edge is the same kind of problem, and a value encoded as
ASCII for an HTTP header fails on the no-break space, which is in
Latin-1 but not in ASCII:

```python
def header_value(value: str) -> str:
    return value.encode("ascii").decode("ascii")
```

```text
for value in L[latin-1], header_value(value) == value
    falsified   value = '\xa0': raised UnicodeEncodeError

for value in L[ascii], header_value(value) == value
    holds
```

`in` and `not in` hold an output to a language or keep something out of
it:

```text
for title in L[unicode], slugify(title) in L[slug]
    falsified   title = '': '' is not in L[slug]

for body in L[unicode], "<" not in render_comment(body)
    holds
```

A title with no letter or digit in it slugifies to the empty string,
which is not a slug, so the post would have no URL, while the comment
renderer escapes every `<` whatever text it is given.

Formats are languages too, each decided by the parser Python already
has: `L[json]` is what `json.loads` accepts, `L[uuid]` what `uuid.UUID`
reads, `L[iso_date]` what `date.fromisoformat` reads on your Python. A
config normaliser that loads a JSON document and writes it back out
shows why the parser's own reading matters:

```text
for text in L[json], normalise_config(normalise_config(text)) == normalise_config(text)
    falsified

for text in L[json, depth <= 100], normalise_config(normalise_config(text)) == normalise_config(text)
    holds
```

From Python 3.12 the parser accepts documents nested almost ten thousand deep, but
writing one back out recurses once per level and stops at the recursion
limit. A document nested a thousand deep loads and then can't be saved,
and bounding the depth the service accepts makes the claim hold.

| Language | Every string that | Decided by |
|---|---|---|
| `unicode` | is a `str`, lone surrogates included | |
| `ascii`, `latin-1` | uses only those code points | `ord(c)` |
| `printable` | prints | `str.isprintable` |
| `digit`, `alpha`, `alnum` | is made of ASCII digits, letters, or both | the ASCII sets |
| `unicode_alpha`, `unicode_alnum` | is letters, or letters and digits, in any script | `str.isalpha`, `str.isalnum` |
| `identifier` | is a Python identifier | `str.isidentifier` |
| `json` | Python's JSON parser accepts | `json.loads` |
| `uuid` | `uuid.UUID` reads, in any of its spellings | `uuid.UUID` |
| `iso_date`, `iso_datetime` | `fromisoformat` reads | `fromisoformat` |
| `ipv4`, `ipv6` | is an address | `ipaddress` |
| `base64`, `hex` | decodes | `b64decode(validate=True)`, `bytes.fromhex` |
| `slug` | is lower-case words joined by single hyphens | `[a-z0-9]+(-[a-z0-9]+)*` |
| `shell_safe` | a shell reads literally | `shlex.quote(s) == s` |

`len <= 32` inside the brackets bounds a language's length, and
`L[ascii] \ {""}` leaves out the empty string, which every alphabet
language includes. The characters text code tends to get wrong are
languages of their own, `control`, `invisible`, `combining`,
`surrogate`, `compatibility` and `astral`, for a claim about exactly
them.

## Records and schemas

Whatever already describes a record is a language of those records:
`L[shop.db.Order]` is every row the orders table accepts, and
`L[shop.forms.SignupForm]` every form pydantic validates. Membership is
decided by the library itself, so a record is in the language exactly
when your application would accept it.

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
for order in L[shop.db.Order], order_total(order) >= 0
    proven

for form in L[shop.forms.SignupForm], 0 <= years_until_adult(form) <= 5
    proven
```

Both are proven over every order and every form, from the table's CHECK
constraints and the model's `Field` bounds. Where a function reads a
field the proof can't reason about, the record says which one and the
claim is checked instead.

A JSON Schema is the language of the documents it validates, so a
webhook handler can be checked against every event the provider's
schema allows, including one its router doesn't handle:

```text
for event in L[shop.webhooks.CHARGE_EVENT], queue_for(event) in {"billing", "alerts"}
    falsified   event = {'type': 'charge.refunded', 'amount': 0}: raised KeyError
```

A claim can also reach into a record, through fields and indices, at
any depth, with `[*]` for every element, and the witness is shrunk at
every level so it keeps only what the failure needs:

```text
for cart in L[shop.forms.Cart], largest_quantity(cart) <= 3
    falsified   cart = Cart(items=[CartItem(sku='', quantity=4)]): 4 vs 3

for cart in L[shop.forms.Cart], cart.items[*].quantity in [1, 3], largest_quantity(cart) <= 3
    holds
```

A bound on a path means the value is there. Where a path can reach
nothing, such as a field holding `None` or the first item of an empty
basket, the record is outside the bound unless the claim keeps it in
with `| {absent}`.

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
for comment in L[shop.threads.Comment, depth <= 50], thread_size(comment) >= 1
    proven

for comment in L[shop.threads.Comment], thread_size(comment) >= 1
    falsified   comment = <Comment tree 1050 records deep>: raised RecursionError
```

The first is proven by induction. The second is the same function over
threads of any depth, where the arithmetic is still right and the code
isn't: a reply chain a thousand deep runs out of Python's recursion, and
the language includes one among its hazards. `depth`, `nodes` and
`width` bound a tree inside the brackets, counted in records.

## When a function refuses input

Some functions reject part of their input on purpose, such as a parser
raising `ValueError` or Django's `get_valid_filename` raising
`SuspiciousFileOperation` for a name it can't use. A claim over a
language that still holds those inputs is falsified, because the
language is wider than the function's domain. `refused_inputs` shows
what is refused, and `narrow_language` gives the language without it,
for the claim to quantify over instead. [Narrow a language to what a
function accepts](docs/how-to-narrow-a-language.md) walks through it.

## Adaptors

An adaptor reads one library's schema objects. Where the library has its
own validator, that validator decides membership.

| Adaptor | Reads | Membership decided by |
|---|---|---|
| pydantic | a `BaseModel` subclass, with `Field` bounds and constraints | `model_validate` |
| SQLAlchemy | a mapped class or a `Table`, with types, `nullable` and CHECK constraints | the database's own constraints, in an in-memory SQLite |
| Django | a `Model` subclass, with field types, options and validators | `full_clean` |
| JSON Schema | a schema as a dict, local `$ref` included | the `jsonschema` validator |
| dataclass | a dataclass, with `Annotated` bounds | the package's checker |
| TypedDict | a `TypedDict`, with `Annotated` bounds | the package's checker |
| text | a `str` parameter, and `Annotated[str, MaxLen(n)]` | the text languages |

The library adaptors are optional extras (`pip install
"mathema-language[pydantic]"`, `[sqlalchemy]`, `[django]`,
`[jsonschema]`, or `[all]`), and none imports its library unless the
object in front of it came from that library. An adaptor for another
library is an ordinary registration under the
`mathema.language_adaptors` entry point; [writing an
adaptor](docs/adaptors.md) gives the contract and the checks its tests
can call.

## Where next

- [The tutorial](docs/tutorial-first-claim.md), six short pages read in
  order, starting from a real Django test.
- [What to claim](docs/catalogue.md): the claims worth writing for a
  parser, a renderer, a normaliser, a validator or an escaper.
- [The reference](docs/index.md): every language, refinement, adaptor
  and built-in claim.
- A language of your own is any object meeting
  `mathema.languages.Language`, registered with `register_language`,
  under a `mathema.languages` entry point, or named by its dotted path,
  `L[myapp.text.SKU]`.

## Requirements

Python 3.10 or later and mathema 0.6.1 or later, before 0.7. The package
imports only from `mathema.interfaces.extension`, the surface mathema
versions for extension authors, and a test pins that.

## Licence

Apache-2.0. mathema itself is licensed separately.
