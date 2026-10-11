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

## Notes on the parser

Some defects in a parser are accepted by argparse when the parser is
built and show up only when the program runs. Reading a parser, for
either language on this page, warns with each one it finds
(`ParserNoteWarning`), and `parser_notes` returns them:

```python
import argparse

from mathema_language.argv import parser_notes

report = argparse.ArgumentParser(prog="report")
report.add_argument("--detailed", type=bool, default=False)
report.add_argument("--format", choices=["csv", "json"], default="text")
report.add_argument("--limit", type=int, default="all")
for note in parser_notes(report):
    print(note)
```

<!-- output -->
```text
report: argument --detailed: type=bool reads every non-empty value as True, so `--detailed False` gives True; a flag is action='store_true' or argparse.BooleanOptionalAction
report: argument --format: the default 'text' is not one of the choices ['csv', 'json'], and argparse never checks a default
report: argument --limit: the default 'all' is not a value its type reads (invalid literal for int() with base 10: 'all'), so every command line that leaves it out is refused
```

| note | what argparse does |
|---|---|
| `type=bool` | `bool("False")` is `True`, so any value given turns it on |
| a default outside its choices | the default reaches the program unchecked, while typing the same value is refused |
| a text default its type refuses | the default is converted only when the option is left out, so every command line without it exits with a usage error |
| two options storing into one name | the last one given wins; a `store_true` and `store_false` pair, and alternatives in a mutually exclusive group, are not noted |
| choices the type never produces | `type=int` with `choices=["1", "2"]` refuses every value, and `type=str.lower` never gives a choice spelled in capitals |
| help that fails to format | `--help` raises instead of printing, usually a `%` that should be `%%` |

The notes cover every subcommand, and the parsers in the shop examples
have none.

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

## The command lines themselves

The namespaces are what a handler sees. What a user types is a list of
strings, and those are a language of their own: the command lines the
parser accepts. `argv_language` draws them in every spelling argparse
reads the same way (`--quantity 3` and `--quantity=3`, an unambiguous
abbreviation such as `--q`, options before or after positionals), and
membership is the parser's own, so a refusal is explained in its words:

```python
from mathema_language.argv import argv_language

commands = argv_language(build_parser)
print(commands.explain(["restock", "--quantity", "x", "a"])[0].predicate)
for hazard in commands.hazards()[:6]:
    print(hazard.value)
```

<!-- output -->
```text
shop restock: error: argument --quantity: invalid int value: 'x'
['--help']
['restock', '--help']
['discount', '--help']
['export', '--help']
['restock', '--quantity', '-1', 'a']
['restock', '--quantity=-1', 'a']
```

Its hazards are what command lines break on: `--help` on every
subcommand, a negative number given as a value, an empty value, a value
starting with a dash, an abbreviation, an option given twice. A function
that takes the command line, as a `main` does, is claimed over it:

```python
def units_from_argv(argv: list[str]) -> int:
    """How many units an admin command line orders, 0 when it only asks
    for help."""
    try:
        args = build_parser().parse_args(argv)
    except SystemExit:
        return 0
    return units_ordered(args)
```

Until the claim can name the language directly, register it under a
name of your own:

```python
import mathema.languages

mathema.languages.register_language("shop_admin_argv", commands)
```

```text
f = units_from_argv
for argv in L[shop_admin_argv], f(argv) >= 0
    falsified   argv = ['restock', '--quantity', '-1', 'a']: -12 vs 0
```

The witness is the command line itself: `shop restock --quantity -1 a`
orders minus twelve units.
