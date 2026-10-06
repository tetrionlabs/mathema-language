# Records

<!-- shop: forms db -->
<!-- requires: pydantic -->
<!-- requires: sqlalchemy -->

A record is a value with named fields: a pydantic model, a dataclass, a
row of a SQLAlchemy or Django table, a JSON document with a schema. The
schema already says which records are valid, so a claim over records
doesn't need a new domain. It names the schema you have.

## The schema is the domain

The shop's signup form:

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

`L[shop.forms.SignupForm]` is every `SignupForm` pydantic would accept,
named by the class's dotted path. mathema asks pydantic itself whether a
record is a member, so the constraints mean exactly what they mean in
your application.

## A proof over every record

The site hides adult content until a user turns 18:

```python
def years_until_adult(form: SignupForm) -> int:
    """How long until the user may see adult content."""
    return max(0, 18 - form.age)
```

```text
for form in L[shop.forms.SignupForm], 0 <= years_until_adult(form) <= 5
    proven
```

`proven`, although there are infinitely many forms. mathema read
`years_until_adult`, saw that it only uses `age`, and turned the field
into a symbol bounded by the schema, `13 <= age <= 120`; from there the
bound on `max(0, 18 - age)` is algebra. This is the thing a record
schema buys you that a string doesn't: its fields are numbers and
bounded strings mathema can reason about, not just sample.

A claim that is one year too tight is caught with the record that
breaks it:

```text
for form in L[shop.forms.SignupForm], years_until_adult(form) <= 4
    falsified   form = SignupForm(username='aaa', age=13): 5 vs 4
```

## A table is a schema too

The orders table, with its constraints in the database:

```python
class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(sa.String(12), sa.CheckConstraint("length(sku) >= 3"))
    quantity: Mapped[int] = mapped_column(sa.CheckConstraint("quantity BETWEEN 1 AND 100"))
    unit_price: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2),
                                                sa.CheckConstraint("unit_price >= 0"))
```

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

A checkout holds a cart, which holds a list of items:

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
└── postcode   str of at most 8 characters, or None
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
    falsified   checkout = Checkout(cart=Cart(items=[]), postcode=''): 0 vs 7
```

This says "for every checkout whose first quantity is 7", and it fails
on a checkout with no first item at all. A path into a list that may be
empty doesn't insist the element exists; an empty basket has no first
quantity to constrain. To say the element must be there, leave out the
missing case, `\ {missing}`, as the previous pages left out values:

```text
for checkout in L[shop.forms.Checkout], checkout.cart.items[0].quantity in [7, 7] \ {missing}, first_quantity(checkout) == 7
    holds
```

Next: [Trees](tutorial-trees.md).
