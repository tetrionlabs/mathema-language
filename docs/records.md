<!-- github-only -->
> This page is part of the mathema documentation, [read it on the site](https://mathema.tetrionlabs.com/language/reference/records/).
<!-- /github-only -->

# Records and schemas

<!-- shop: db forms webhooks -->

A function that takes a record, a row, a form or a message is claimed
over the schema that already describes it. Whatever describes a record
names a language of them: a pydantic model, a dataclass, a TypedDict, a
SQLAlchemy table, a Django model or a JSON Schema, written by its dotted
path, `L[shop.db.Order]`. A parameter annotated with the class infers
its language on its own. Membership is decided by the library's own
validator where it has one, so a record is valid exactly when your
application's own library says so.

| Schema | Written | Membership decided by |
|---|---|---|
| a pydantic model | `L[shop.forms.SignupForm]` | `model_validate` |
| a SQLAlchemy table or mapped class | `L[shop.db.Order]` | inserting the row into in-memory SQLite |
| a Django model | `L[shop.reviews.Review]` | `full_clean` |
| a JSON Schema, as a dict | `L[shop.webhooks.CHARGE_EVENT]` | the `jsonschema` validator |
| a dataclass | `L[shop.shipping.Parcel]` | the package's own checker |
| a TypedDict | `L[shop.search.SearchHit]` | the package's own checker |

Each has a page of its own under the reference, saying what it reads
and a worked claim. The examples here are the shop's orders table,
forms and payment webhook.

## Proving a claim over a record

Where a function reads numeric fields, and text fields only through
`len`, the derive route lifts each field it reads to a symbol bounded
by the schema, and the ordinary prover runs, so a claim over every
record is proven rather than sampled:

```python
class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(sa.String(12), sa.CheckConstraint("length(sku) >= 3"))
    quantity: Mapped[int] = mapped_column(sa.CheckConstraint("quantity BETWEEN 1 AND 100"))
    unit_price: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2),
                                                sa.CheckConstraint("unit_price >= 0"))


def order_total(order: Order) -> Decimal:
    """What the customer pays for the order."""
    return order.quantity * order.unit_price
```

```text
f = order_total
for order in L[shop.db.Order], f(order) >= 0
    proven

for order in L[shop.db.Order], f(order) <= 10000
    falsified   order = Order(id=0, sku='aaa', quantity=1, unit_price=Decimal('10742.34')): Decimal('10742.34') vs 10000
```

The table's CHECK constraints bound the quantity and the price from
below, so the total is never negative; nothing bounds the price from
above. A falsified claim's witness is a real record the database
accepts, shrunk until only what the failure needs is left: the
`sku` is the shortest the CHECK allows, the quantity is one.

## A schema written as data

A JSON Schema is the language of the documents it validates, which is
how a webhook handler meets every event the provider can send:

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
```

```text
f = queue_for
for event in L[shop.webhooks.CHARGE_EVENT], f(event) in {"billing", "alerts"}
    falsified   event = {'type': 'charge.refunded', 'amount': 0}: raised KeyError
```

## Paths into a record

A binding can narrow the records a claim covers by naming a path into
them, through fields and indices, at any depth: `checkout.postcode`,
`checkout.cart.items[0].quantity`, and `[*]` for every element. A bound
on a path means the value is there: a record whose path reaches nothing
(a field holding `None`, a key that is not there, an index past the
end) is absent there and outside the bound, and `| {absent}` keeps it
in. [Relations and paths](paths.md) has the two kinds of nothing.

```python
class Checkout(BaseModel):
    cart: Cart
    postcode: str | None = Field(default=None, max_length=8)


def needs_postcode(checkout: Checkout) -> bool:
    """Whether the checkout page still has to ask for a postcode."""
    return checkout.postcode is None


def first_quantity(checkout: Checkout) -> int:
    """The quantity of the first item, 0 for an empty basket."""
    items = checkout.cart.items
    return items[0].quantity if items else 0
```

```text
f = needs_postcode
for checkout in L[shop.forms.Checkout], f(checkout) == False
    falsified   checkout = Checkout(cart=Cart(items=[]), postcode=None): True vs False

for checkout in L[shop.forms.Checkout], checkout.postcode in L[alnum], f(checkout) == False
    holds

f = first_quantity
for checkout in L[shop.forms.Checkout], checkout.cart.items[*].quantity in [1, 3], f(checkout) <= 3
    holds

for checkout in L[shop.forms.Checkout], checkout.cart.items[0].quantity in [7, 7], f(checkout) == 7
    holds

for checkout in L[shop.forms.Checkout], checkout.cart.items[0].quantity in [7, 7] | {absent}, f(checkout) == 7
    falsified   checkout = Checkout(cart=Cart(items=[]), postcode=''): 0 vs 7
```

The last is falsified by an empty basket: `items[0]` is past the end of
the list, so the path is absent there, and `| {absent}` brought that
checkout into the claim.

## Enforcing the schema

A function whose job is to guard a boundary should refuse a record its
schema rejects, and `excluded_outside_domain` feeds it records just
outside the language. A witness names the value and why it is outside,
in the library's own words:

```python
def welcome_message(form: SignupForm) -> str:
    """The first line of the welcome email."""
    return f"Welcome, {form.username}!"
```

```text
f = welcome_message
for form in L[shop.forms.SignupForm], excluded_outside_domain(form)
    falsified   form = SignupForm(username='aaa', age=12) (outside L[shop.forms.SignupForm] at .age: Input should be greater than or equal to 13) is outside the declared domain but was accepted
```

That is fine for a function that trusts pydantic to have validated the
form already, and the claim is the one to write for the function that
loads it, from a request or a database, where nothing has.

## Recipes

| To say | Write |
|---|---|
| a computed value stays in range for every record | `for order in L[shop.db.Order], f(order) >= 0` |
| a handler copes with every document the schema allows | `for event in L[shop.webhooks.CHARGE_EVENT], is_language_defined(event)` |
| every element of a list field is within bounds | `for c in L[shop.forms.Checkout], c.cart.items[*].quantity in [1, 3], ...` |
| a field is present, not absent | `c.postcode in L[alnum]` |
| a boundary refuses what the schema rejects | `for form in L[shop.forms.SignupForm], excluded_outside_domain(form)` |
