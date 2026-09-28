# Quick start

<!-- shop: text db threads -->

mathema checks claims about code: it proves them where it can, and
where a claim is wrong it finds a real input that breaks it. Every claim
quantifies over a domain, and for a function of numbers that is `R` or
`[0, 1]`. This package supplies the domains for what most application
code actually takes: strings, records and the schemas that describe
them, each written `L[...]`.

```
pip install mathema-language
```

mathema finds it through its entry points once installed, so there is
nothing to configure. Three claims show the three kinds of data, each on
the shop in `examples/shop`, the example application these pages use
throughout.

## A string

```python
def display_name(username: str) -> str:
    """The username as shown in the header, upper-cased."""
    return username.upper()
```

```text
f = display_name
for username in L[unicode, len <= 32], len(f(username)) <= 32
    falsified   ('aﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁ'): 33 vs 32
```

`L[unicode, len <= 32]` is every string of at most 32 code points.
`falsified` means mathema ran the function on a member of the domain
and the claim did not hold, and the witness is that member, shrunk to
the smallest one that still fails: `ﬁ` is one code point and upper-cases
to two.

## A record

```python
def order_total(order: Order) -> Decimal:
    """What the customer pays for the order."""
    return order.quantity * order.unit_price
```

```text
f = order_total
for order in L[shop.db.Order], f(order) >= 0
    proven
```

`L[shop.db.Order]` is every row the SQLAlchemy orders table accepts.
`proven` means the claim holds for every one of them: the fields the
function reads were lifted to symbols bounded by the table's CHECK
constraints, and the proof went through.

## A tree

```python
def thread_size(comment: Comment) -> int:
    """How many comments the thread holds, this one included."""
    return 1 + sum(thread_size(r) for r in comment.replies)
```

```text
f = thread_size
for comment in L[shop.threads.Comment, depth <= 50], f(comment) >= 1
    proven

for comment in L[shop.threads.Comment], f(comment) >= 1
    falsified   (<Comment nested 2100 levels deep (1050 Comment records)>): raised RecursionError
```

The first is proven by structural induction. The second is the same
function on threads of any depth, where the recursion runs out: the
mathematics is right and the code is not.

## What the verdicts mean

| Verdict | Meaning |
|---|---|
| `proven` | true for every member of the domain, by a proof |
| `holds` | true on every input mathema tried, the language's hazards first |
| `falsified` | false, with a real input as the witness |
| `unknown` | mathema could not decide it, and says why |
| `skipped` | the claim could not be run, and the record says why |

## Where next

- For text: [Text](text.md), [Formats and identifiers](formats.md) and
  [JSON](json.md).
- For records: [Records and schemas](records.md) and [Trees](trees.md).
- Everything by name: [Languages](languages.md),
  [Refinements](refinements.md), [Relations and paths](paths.md),
  [Claim families](families.md), [Vocabulary](vocabulary.md), and a page
  for each adaptor.
- The claims worth writing for a function, by what the function does:
  [What to claim](catalogue.md).
