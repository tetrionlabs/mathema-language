<!-- github-only -->
> This page is part of the mathema documentation, [read it on the site](https://mathema.tetrionlabs.com/language/reference/tutorial-records/).
<!-- /github-only -->

# Records

<!-- shop: forms db -->
<!-- requires: pydantic -->
<!-- requires: sqlalchemy -->

A record is a value with named fields: a pydantic model, a dataclass, a
row of a SQLAlchemy or Django table, a JSON document with a schema. The
schema already says which records are valid, so a claim over records
doesn't need a new domain. It names the schema you have.

## The schema is the domain

The shop's signup form is a pydantic model, defined in `shop/forms.py`
next to the functions that use it:

```python
class SignupForm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=32)
    age: int = Field(ge=13, le=120)
```

```text
SignupForm
├── username   str, 3 to 32 characters
└── age        int, 13 to 120
```

`L[shop.forms.SignupForm]` is every `SignupForm` pydantic would accept.
The name inside the brackets is the class's dotted path, the module
`shop.forms` and then the class, and mathema imports it from there the
way `from shop.forms import SignupForm` would. So the schema stays where
your application already defines it, at the top level of a module, and
the claim refers to it by name. You don't copy it into the claim, a
claims file or a script, and a schema defined only inside a test or a
function can't be named at all. mathema asks pydantic itself whether a
record is a member, so the constraints mean exactly what they mean in
your application.

## A proof over every record

Some of the shop's products are sold only to customers aged 18 or over,
and a function in the same module works out from the form how long a
younger user has to wait:

```python
def years_until_eighteen(form: SignupForm) -> int:
    """How many years until the user turns 18."""
    return max(0, 18 - form.age)
```

The function and the record happen to share a module here, but they
needn't: the claim names the function by name and the record by dotted
path, and either can live anywhere Python can import it from. Kept in
the function's docstring, the claim is:

```python
def years_until_eighteen(form: SignupForm) -> int:
    """How many years until the user turns 18.

    Claims:
        at_most_five_years: for form in L[shop.forms.SignupForm], 0 <= years_until_eighteen(form) <= 5
    """
    return max(0, 18 - form.age)
```

and checked, with `mathema check shop/forms.py:years_until_eighteen`:

```text
for form in L[shop.forms.SignupForm], 0 <= years_until_eighteen(form) <= 5
    proven
```

`proven`, although there are infinitely many forms. mathema read
`years_until_eighteen`, saw that it only uses `age`, and turned the field
into a symbol bounded by the schema, `13 <= age <= 120`; from there the
bound on `max(0, 18 - age)` is algebra. This is the thing a record
schema buys you that a string doesn't: its fields are numbers and
bounded strings mathema can reason about, not just sample.

A claim that is one year too tight is caught with the record that
breaks it:

```text
for form in L[shop.forms.SignupForm], years_until_eighteen(form) <= 4
    falsified   form = SignupForm(username='aaa', age=13): 5 vs 4
```

## A table is a schema too

The orders table is a SQLAlchemy model in `shop/db.py`, with its
constraints in the database:

```python
class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(sa.String(12), sa.CheckConstraint("length(sku) >= 3"))
    quantity: Mapped[int] = mapped_column(sa.CheckConstraint("quantity BETWEEN 1 AND 100"))
    unit_price: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2),
                                                sa.CheckConstraint("unit_price >= 0"))
```

and the function that totals an order sits beside it:

```python
def order_total(order: Order) -> Decimal:
    """What the customer pays for the order."""
    return order.quantity * order.unit_price
```

`L[shop.db.Order]` is every row the table accepts: mathema inserts each
candidate into an in-memory SQLite copy of the table and rolls back, so
the CHECK constraints are the database's own.

```text
for order in L[shop.db.Order], order_total(order) >= 0
    proven

for order in L[shop.db.Order], order_total(order) <= 10000
    falsified   order = Order(id=0, sku='aaa', quantity=1, unit_price=Decimal('10742.34')): Decimal('10742.34') vs 10000
```

The first is proven from the constraints: a quantity of at least 1
times a price of at least 0. The second is the kind of assumption that
lives in a payment integration's limits. Nothing in the table stops a
single item costing more than 10,000, so either the table needs a
constraint or the integration needs to handle it.

## Paths into a record

A checkout holds a cart, which holds a list of items, all three
pydantic models in `shop/forms.py`:

```python
class CartItem(BaseModel):
    sku: str
    quantity: int = Field(ge=1, le=10)


class Cart(BaseModel):
    items: list[CartItem]
```

```python
class Checkout(BaseModel):
    cart: Cart
    postcode: str | None = Field(default=None, max_length=8)
```

```text
Checkout
├── cart: Cart
│   └── items: list[CartItem]
│       ├── [0]: CartItem
│       │   ├── sku        str
│       │   └── quantity   int, 1 to 10
│       └── [1], [2], …
└── postcode   str of at most 8 characters, or None (absent)
```

A path names one place in that tree, spelled the way Python reaches it:
`checkout.cart.items[0].quantity` is the first item's quantity, and
`checkout.cart.items[*].quantity` is every item's. A path can narrow the
domain the way a refinement does, which lets a claim talk about one
part of a record:

```python
def first_quantity(checkout: Checkout) -> int:
    """The quantity of the first item, 0 for an empty basket."""
    items = checkout.cart.items
    return items[0].quantity if items else 0
```

```text
for checkout in L[shop.forms.Checkout], checkout.cart.items[0].quantity in [7, 7], first_quantity(checkout) == 7
    holds
```

This says "for every checkout whose first quantity is 7", and a bound
on a path means the value is there: a checkout with an empty basket has
no first quantity, so it is not one of the checkouts this claim is
about. Sometimes the place a path names can hold nothing, and mathema
tells two kinds of nothing apart:

```text
checkout.postcode = None             absent: the field has no value
checkout.cart.items[0], items = []   absent: there is no first item
{"note": ...} with no "note" key     absent: the key is not there
checkout.cart.items[1] = None        a hole: a list slot holding nothing
price = nan                          a hole: a number with no value
```

Something is absent when the object isn't there at all, and a hole is
a slot that exists but holds no value. To make a claim cover the absent
case too, admit it in the bound with `| {absent}`:

```text
for checkout in L[shop.forms.Checkout], checkout.cart.items[0].quantity in [7, 7] | {absent}, first_quantity(checkout) == 7
    falsified   checkout = Checkout(cart=Cart(items=[]), postcode=''): 0 vs 7
```

Now the empty basket is covered, and `first_quantity` returns 0 for it,
which the claim didn't allow. Both claims are true statements about
the code; they just cover different checkouts, and the bound says which.

Next: [Trees](tutorial-trees.md).
