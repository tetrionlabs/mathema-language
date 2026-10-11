<!-- github-only -->
> This page is part of the mathema documentation, [read it on the site](https://mathema.tetrionlabs.com/language/reference/adaptor-argparse/).
<!-- /github-only -->

# Command lines (argparse)

<!-- shop: admin -->

The argparse adaptor reads an `argparse.ArgumentParser` as the language
of the namespaces its `parse_args` returns, so a function that takes
`args` is claimed over every namespace the command line can produce.
It reads a parser object, or a function that builds one when the
function takes no arguments and is annotated to return an
`ArgumentParser`, which is how most command lines are written. Members
are `argparse.Namespace` objects, checked by the neutral checker.

## What it reads

| argparse | Namespace field | Notes |
|---|---|---|
| `add_argument(dest, type=int)`, `float`, `str` | an int, a float, text | a default given as text is converted with `type`, as argparse converts it |
| any other `type` (`Path`, a function) | drawn as text and converted with it | |
| `choices=[...]` | one of the choices | |
| `nargs="?"`, `"*"`, `"+"`, a number | a value or `None`, a list, a list of at least one, a list of that length | |
| `action="store_true"`, `"store_false"` | a bool | |
| `BooleanOptionalAction` | a bool, or `None` with no default | |
| `action="store_const"`, `"append_const"` | the constant or the default, a list of the constant | |
| `action="count"` | an int from its default up | |
| `action="append"`, `"extend"` | a list, or `None` with no default | |
| `add_subparsers(dest=...)` | one shape of namespace per subcommand, its name in `dest` | an alias gives the same shape |
| `set_defaults(func=...)` | a field holding that value | |
| `--help`, `--version` | none | they end the program instead |

A namespace only exists for a command line the parser accepts, so every
member is one a user can produce. What the parser accepts is often more
than the code expects: `type=int` takes `-1`.

## A worked claim

The shop's admin command line, from `examples/shop/admin.py`:

```python
def build_parser() -> argparse.ArgumentParser:
    """`shop restock SKU [--quantity N]`, `shop discount --percent P`
    and `shop export [--to PATH]`."""
    parser = argparse.ArgumentParser(prog="shop")
    parser.add_argument("--verbose", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    restock = commands.add_parser("restock")
    restock.add_argument("sku")
    restock.add_argument("--quantity", type=int, default=1)
    discount = commands.add_parser("discount")
    discount.add_argument("--percent", type=int, required=True)
    export = commands.add_parser("export")
    export.add_argument("--to", type=Path, default=Path("orders.csv"))
    return parser


def units_ordered(args: argparse.Namespace) -> int:
    """How many units a command orders from the supplier, in cases of 12."""
    if args.command == "restock":
        return args.quantity * 12
    return 0


def discounted(args: argparse.Namespace, price: float) -> float:
    """A price after the discount command's percentage."""
    if args.command == "discount":
        return price * (100 - args.percent) / 100
    return price
```

```text
f = units_ordered
for args in L[shop.admin.build_parser], f(args) >= 0
    falsified   args = Namespace(verbose=False, command='restock', sku='', quantity=-1): -12 vs 0

for args in L[shop.admin.build_parser], args.quantity in [1, 100], f(args) <= 1200
    holds

f = discounted
for args in L[shop.admin.build_parser], price in [0, 1000], f(args, price) <= price
    falsified   args = Namespace(verbose=False, command='discount', percent=-1), price = 500: 505.0 vs 500.0
```

`shop restock '' --quantity -1` parses, and orders minus twelve units.
`shop discount --percent -1` parses too, and raises every price. The
path bound in the second claim keeps the namespaces that have a
quantity, so the other two subcommands are outside it, and within it
the order is at most 1,200 units.

The fix belongs where the input arrives: a `type` that refuses what the
code cannot use. A `type` the neutral model does not know is drawn as
text and passed through it, so a function such as

```python title="a type that refuses a negative quantity"
def positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value
```

turns the first falsification into a usage error at the command line.
