# mathema-language

**mathema for strings, records and schemas.**

mathema checks claims about code, proving them where it can and
falsifying them with a real input where they are wrong, and every claim
quantifies over a domain. For a function of numbers that domain is `R`
or `[0, 1]`. This package supplies the domains for everything else a
function takes: strings (`L[ascii]`, `L[json]`, `L[slug]`), records (a
dataclass, a TypedDict, a pydantic model), and the schemas that describe
them (a JSON Schema, a SQLAlchemy table, a Django model), each written
the same way, `L[...]`.

```
pip install mathema-language
```

mathema finds the package through its entry points once installed, so
there is nothing to configure. Without it, mathema still parses and
records an `L[...]` domain but resolves no name, and a claim over one is
skipped with the reason.

## Strings

```
for s in L[unicode], len(f(s)) == len(s)        f = str.upper
    falsified   ('ﬁ'): 2 vs 1

for s in L[latin-1], f(s) == s                   f = ascii_only
    falsified   ('\xa0'): raised UnicodeEncodeError

for s in L[ascii], f(s) == s                     f = ascii_only
    holds       n=192
```

Upper-casing looks as though it keeps a string's length, and over the
whole of Unicode it does not: the ligature `ﬁ` upper-cases to the two
letters `FI`. A probe drawing random letters would almost never try it
and would report `holds` for a claim that is false. Every language here
visits its hazards first, the strings real code mishandles, collected
from what the test suites of Django, Werkzeug, MarkupSafe, ftfy and
CPython found the hard way, so `ﬁ` is among the first strings tried
rather than a lucky draw. The second and third claims are the same
lesson at an alphabet boundary: a function that encodes as ASCII fails
on the no-break space, which is latin-1 but not ASCII, and over
`L[ascii]` it holds.

Each language is decided by Python's own reading of it, never a regular
expression standing in for a parser:

| Name | Members | Membership |
|---|---|---|
| `unicode` | every `str`, lone surrogates included | none needed |
| `ascii`, `latin-1` | strings over those code points | `ord(c) < 128`, `< 256` |
| `printable` | what Python calls printable | `str.isprintable` |
| `digit` | strings over the ten ASCII digits | `c in "0123456789"` |
| `alpha`, `alnum` | letters, and letters with digits, any script | `str.isalpha`, `str.isalnum` |
| `identifier` | Python identifiers | `str.isidentifier` |
| `json` | JSON documents | `json.loads` |
| `uuid` | every spelling `uuid.UUID` reads | `uuid.UUID` |
| `iso_date`, `iso_datetime` | ISO 8601 dates and times | `fromisoformat` |
| `ipv4`, `ipv6` | addresses | `ipaddress` |
| `base64`, `hex` | encoded bytes | `b64decode(validate=True)`, `bytes.fromhex` |
| `slug` | lower-case words joined by single hyphens | `[a-z0-9]+(-[a-z0-9]+)*` |
| `shell_safe` | a word a shell reads literally | `shlex.quote(s) == s` |

An alphabet language includes the empty string, the way a Kleene star
reads, and `L[ascii] \ {""}` leaves it out. The characters parsers tend
to get wrong are languages of their own, so a claim can quantify over
exactly them: `c0`, `format`, `combining`, `surrogate`, `nfkc_folding`
and `non_bmp`.

A language can carry a length bound, counted in code points the way
`len` counts, and the members at the bound and one past it are among
the first values tried, so a function that truncates at eighty is held
to exactly that:

```
for s in L[unicode, len <= 80], f(s) == s        f = headline (cuts at 80)
    holds       n=224

for s in L[unicode, len <= 81], f(s) == s
    falsified   ('aaaa…a', 81 characters)
```

With `in` and `not in`, a claim holds an output to a language or keeps
a token out of it:

```
for s in L[unicode], f(s) in L[slug]             f = slugify
    falsified   (''): '' is not in L[slug]

for s in L[unicode], "<" not in f(s)             f = escape_html
    holds       n=224
```

The first is falsified by any input with no ASCII letter or digit in it,
which slugifies to the empty string, and the empty string is not a
slug.

## Records and schemas

Whatever describes a record is a language too, and names its records:
a dataclass, a TypedDict, a pydantic model, a JSON Schema, a SQLAlchemy
table or a Django model, read into one neutral model and checked by the
library's own validator where it has one. A parameter annotated with the
class infers its language on its own.

```python
@dataclass
class Line:
    sku: Annotated[str, MaxLen(8)]
    qty: Annotated[int, Ge(1), Le(10)]
    price: Annotated[float, Ge(0.0)]

def line_total(line: Line) -> float:
    return line.qty * line.price
```

```
for line in L[myapp.Line], f(line) >= 0
    proven      (derive)
```

That claim is proven, not sampled: the fields the body reads become
symbols bounded by the schema (`qty` a whole number from one to ten,
`price` a real at least zero), and the ordinary prover runs. Where the
body reads a field the proof has no reading of, it says which, and the
claim is sampled instead.

A binding reaches into a record at any depth, through fields and
indices, and `[*]` means every element:

```
for o in L[myapp.Order], o.lines[*].qty in [1, 3], f(o) <= 3     f = largest_qty
    holds       n=192

for o in L[myapp.Order], f(o) <= 3
    falsified   (Order(address=Address(zip=''), lines=[OrderLine(qty=6)])): 6 vs 3
```

A path past the end of a list, or through a missing field, reaches the
missing value, and `\ {missing}` on the bound says the path must be
there.

## Trees

A record that refers to itself is a language of trees, and so is a JSON
Schema whose `$ref` points back into itself. Three bounds apply inside
the brackets, counted in records: `depth` (records along the deepest
path), `nodes` (records in all) and `children` (the most any one record
holds). Over `L[json]` they count containers instead.

```python
@dataclass
class Branch:
    label: int
    children: list[Branch] = field(default_factory=list)

def tree_size(t: Branch) -> int:
    return 1 + sum(tree_size(c) for c in t.children)
```

```
for t in L[myapp.Branch, depth <= 20], f(t) >= 1
    proven      (derive:induction)

for t in L[myapp.Branch], f(t) >= 1
    falsified   (<Branch nested 2100 levels deep (1050 Branch records)>): raised RecursionError
```

The first is proven by structural induction: true for a leaf, and true
for a node whenever it is true of each child. It reaches claims about
folds over the children, such as a tree's size, its height or the sum of
a field, and says why when a claim is outside that class. The second is
the same function over trees of any depth, and there the mathematics is
still right while the implementation is not, because Python's recursion
stops at about a thousand frames. The probe builds that tree, and the
witness is summarised because it is too deep to print. Hazards on these
axes come first as they do for text (the empty tree, the deepest and
widest the bounds allow, and the tree one past each bound), draws climb
in depth instead of clustering shallow, and a failing tree is shrunk to
the smallest one that still fails.

## Where next

- [What to claim](docs/catalogue.md): the claims worth writing for a
  parser, renderer, normaliser, validator, escaper or consumer, each
  with a real function and the verdict the test suite holds it to.
- [Rows](docs/rows.md) and [recursive structures](docs/recursive.md), in
  more depth.
- [The adaptors](docs/adaptors.md): one page each for dataclasses,
  TypedDicts, pydantic, JSON Schema, SQLAlchemy and Django, saying what
  each reads and whose validator decides membership, and how to write
  your own.
- Your own language: any object satisfying
  `mathema.languages.Language`, registered with `register_language`,
  under a `mathema.languages` entry point, or named by its dotted path,
  `L[myapp.text.SLUG]`.

## Requirements

Python 3.10 or later and mathema 0.6.1 or later. The package imports
only from `mathema.interfaces.extension`, the surface mathema versions
for extension authors, and a test pins that.

## Licence

Apache-2.0. mathema itself is licensed separately.
