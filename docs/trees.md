# Trees

<!-- shop: threads -->

A schema that refers to itself is a language of trees: a comment and
its replies, a folder and its contents, a category and its
subcategories. A dataclass whose field is a list of itself, a pydantic
model or TypedDict that names itself, and a JSON Schema whose `$ref`
points back into its own document all adapt, and so does `L[json]`,
whose grammar is recursive by definition. Members are finite and
acyclic: a value that contains itself is outside the language, and the
explanation names the place the cycle closes.

The examples on this page are the shop's comment threads, from
`examples/shop/threads.py`:

```python
from dataclasses import dataclass, field


@dataclass
class Comment:
    author: str
    body: str
    replies: list[Comment] = field(default_factory=list)


def thread_size(comment: Comment) -> int:
    """How many comments the thread holds, this one included."""
    return 1 + sum(thread_size(r) for r in comment.replies)


def replies_below(comment: Comment) -> int:
    """How many replies sit under this comment, at any depth."""
    return len(comment.replies) + sum(replies_below(r) for r in comment.replies)


def thread_depth(comment: Comment) -> int:
    """How many levels the thread has, this comment's included."""
    return 1 + max((thread_depth(r) for r in comment.replies), default=0)
```

## Depth, nodes and children

Three refinements bound a tree inside the brackets. On a record tree
they count records: `depth` is the number of records along the deepest
path (a comment with no replies has depth 1), `nodes` is the number of
records, and `children` is the most records any one record holds
directly. On `L[json]`, where every container is a value, they count
containers and values instead (`[[[]]]` has depth 3). Each reads `<=`,
`<`, `>=`, `>` or an interval, and they combine:

```
for comment in L[shop.threads.Comment, depth <= 10], ...
for comment in L[shop.threads.Comment, nodes in [1, 200], width <= 20], ...
for doc in L[json, depth <= 6, width <= 50], ...
```

A bound the schema states itself (`maxItems` on a list, pydantic's
`max_length`) is the language's own. Where nothing bounds a tree the
language stays unbounded, and random members are drawn within stated
sampling bounds (depth 8, 256 nodes, 16 children), which the record
names as sampling choices rather than facts about the language. For
claims about nesting, `depth(v)`, `nodes(v)`, `children(v)` and
`leaves(v)` from `mathema_language.vocabulary.tree` take any nested
dict, list, tuple or record, bound with `let`; having no schema to
read, they count every container, so a comment with an empty list of
replies has depth 2 there.

## What the probe visits

The hazards sit on the structure axes: the empty tree, the deepest and
the widest member the bounds allow (a refinement's own bound among
them, and one past it as the value outside the language), one long
spine, and for an unbounded language a spine past the interpreter's
recursion limit, since a recursive function over an unbounded language
fails there however right its arithmetic is. Where a library's
validator recurses in Python and stops early (the `jsonschema`
validator does, pydantic does not) the language finds that validator's
limit and states it. Random draws climb a depth ladder, 1, 2, 4 and so
on up to the bound, instead of clustering shallow, and a failing tree
is shrunk inside the language by hoisting a subtree into its parent's
place, dropping a reply, then simplifying the fields of each record, so
the witness is the smallest tree that still fails. A witness too deep
to print is summarised by its type and depth.

```text
f = thread_size
for comment in L[shop.threads.Comment], f(comment) >= 1
    falsified   (<Comment nested 2100 levels deep (1050 Comment records)>): raised RecursionError
```

A reply chain a thousand deep exhausts Python's recursion, and the
probe builds one.

## Proof by structural induction

A claim about a recursive function over a tree language can be proven,
not only sampled, when every function it applies is a structural fold:
one `return` of arithmetic over the record's numeric fields, `len` of
its list of children, and `sum`, `max` or `min` of a fold over the
children (with a `default` for `max` and `min`). The derive route
proves the claim for a record with no children, then for a record with
k >= 1 children assuming it of each child, and a numeric field enters
at its lower bound.

```text
f = thread_size
for comment in L[shop.threads.Comment, depth <= 20], f(comment) >= 1
    proven

f = replies_below
for comment in L[shop.threads.Comment, depth <= 20], f(comment) == thread_size(comment) - 1
    proven
```

Both are proven on the route `derive:induction`, and the first record's
sketch reads: by structural induction over replies, the base case (no
replies) and the step (k >= 1 replies, the claim assumed of each) both
hold, and depth <= 20 keeps the recursion under the interpreter's
limit.

The functions are recursive Python, two stack frames per level (the
call and the generator over the replies), so the proof stands only
where the depth bound keeps the recursion under the interpreter's
limit, `depth <= 448` at Python's default limit of 1,000. Over an
unbounded language the mathematics is settled and the implementation is
not, the record says so, and the probe decides, which is how the
unbounded claim above is falsified by a real thread.

The claims it proves: a fold against a constant
(`thread_size(comment) >= 1`), two folds related affinely by `==`
(`replies_below(comment) == thread_size(comment) - 1`), and two folds
related by an ordering where both aggregate with `sum`. Anything else
is declined with the reason and sampled, never disproven by the
induction, since an induction that does not go through says nothing
against the claim:

```text
f = thread_size
for comment in L[shop.threads.Comment, depth <= 20], f(comment) >= 2
    falsified   (Comment(author='', body='', replies=[])): 1 vs 2

for comment in L[shop.threads.Comment, depth <= 20], f(comment) >= thread_depth(comment)
    holds
```

The first is falsified by a single comment, and the record says why
the induction declined: the base case (no replies) does not prove,
`-1 >= 0`. The second is true and sampled, since a sum and a maximum are
not related by this route.

Out of reach for now: mutual recursion between two functions, recursion
through anything but the list of children, functions that carry an
accumulator, and claims that need a stronger statement than themselves
to go through.
