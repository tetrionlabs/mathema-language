# SQLAlchemy

<!-- requires: sqlalchemy -->
<!-- module: sqlalchemy_models -->

The SQLAlchemy adaptor reads a `Table` or a declarative mapped class,
and its members are dicts (for a `Table`) or instances of the class.
What the metadata spells plainly is read into the neutral model and
checked there first; everything else is the database's to decide, by
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
| `CheckConstraint("qty BETWEEN 1 AND 10")`, `"price >= 0"` | `min`, `max` and the exclusive bounds | plain comparisons and `BETWEEN` only |
| any other `CheckConstraint` | not read | decided by the database |
| `unique=True`, `UniqueConstraint`, `ForeignKey` | not checked on a single row | uniqueness and keys are facts about a table, and tables are not part of this release |

## A worked claim

```python
import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Line(Base):
    __tablename__ = "lines"
    __table_args__ = (sa.CheckConstraint("qty BETWEEN 1 AND 10", name="qty_range"),
                      sa.CheckConstraint("price >= 0", name="price_nonneg"),
                      sa.CheckConstraint("length(sku) >= 3", name="sku_long_enough"))
    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(sa.String(8))
    qty: Mapped[int] = mapped_column(sa.Integer)
    price: Mapped[float] = mapped_column(sa.Float)


def line_total(line: Line) -> float:
    """Quantity times price."""
    return line.qty * line.price
```

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `line_total` | `for line in L[sqlalchemy_models.Line], f(line) >= 0` | proven | The lift reads both bounds off the CHECK constraints, a quantity of at least one times a price of at least zero. |
| `line_total` | `for line in L[sqlalchemy_models.Line], f(line) <= 100` | falsified | The price has no upper bound. |

## A non-member

The first record breaks a bound the neutral model read; the second
passes it and is refused by the database, on the CHECK the neutral
model could not read.

```python
from mathema_language.schema.adaptors import adapt_row

language = adapt_row(Line)
for bad in (Line(id=1, sku="ABC", qty=0, price=2.5), Line(id=1, sku="AB", qty=1, price=2.5)):
    for problem in language.explain(bad):
        print(repr(problem.path), "|", problem.predicate)
```

<!-- output -->
```text
'.qty' | >= 1
'' | check sku_long_enough
```
