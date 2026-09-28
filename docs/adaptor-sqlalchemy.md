# SQLAlchemy

<!-- requires: sqlalchemy -->
<!-- shop: db -->

The SQLAlchemy adaptor reads a `Table` or a declarative mapped class,
and its members are dicts (for a `Table`) or instances of the class.
What the metadata spells plainly is read into the neutral model and
checked there first; everything else is left to the database, which decides by
inserting the record into an in-memory SQLite database built from the
table's own DDL, so a CHECK constraint the neutral model cannot read
still decides membership. A mapped class that is also a dataclass
(`MappedAsDataclass`) goes to this adaptor, not the dataclass one. It
needs SQLAlchemy 2.0 or later, `pip install "mathema-language[sqlalchemy]"`,
and is tested at 2.0 and at the latest release.

## What it reads

| SQLAlchemy spelling | Neutral model | Notes |
|---|---|---|
| `Integer`, `SmallInteger`, `BigInteger` | `int` of 32, 16, 64 bits | |
| `Float`, `Numeric(p, s)` | `float`, `decimal(p, s)` | |
| `String(n)`, `Text` | `string`, `max_len` n | a lone surrogate is not a member, since SQLite cannot encode it |
| `Boolean`, `Date`, `Time`, `DateTime`, `Interval`, `LargeBinary` | the matching base type | a timezone-aware `DateTime` is UTC |
| `Enum(...)` | a categorical | |
| `nullable=False` | not nullable | |
| an autoincrement primary key, a default, a server default | not required | |
| `CheckConstraint("quantity BETWEEN 1 AND 100")`, `"unit_price >= 0"`, on the table or on a column | `min`, `max` and the exclusive bounds | plain comparisons and `BETWEEN` only |
| any other `CheckConstraint` | not read | decided by the database |
| `unique=True`, `UniqueConstraint`, `ForeignKey` | not checked on a single row | uniqueness and keys are facts about a table, and tables are not part of this release |

## A worked claim

The shop's orders table, from `examples/shop/db.py`:

```python
import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


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

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `order_total` | `for order in L[shop.db.Order], f(order) >= 0` | proven | The lift reads both bounds off the CHECK constraints, a quantity of at least one times a price of at least zero. |
| `order_total` | `for order in L[shop.db.Order], f(order) <= 10000` | falsified | Nothing bounds the price from above. |

## Enforcing the schema

A function that guards a boundary should refuse a record its schema
rejects. `excluded_outside_domain` feeds it records just outside the
language, and the witness names the value and why it is outside, in
the library's own words. This function trusts its input, so a record
the schema rejects goes straight through:

```python
def receipt_line(order: Order) -> str:
    """The line an order prints on the receipt."""
    return f"{order.quantity} x {order.sku}"
```

```text
f = receipt_line
for order in L[shop.db.Order], excluded_outside_domain(order)
    falsified   order = Order(id=2147483648, sku='', quantity=1, unit_price=Decimal('0')) (outside L[shop.db.Order] at .id: int32)
```

The same claim over the function that loads the record, from a request
or a database, is the one that should hold.
