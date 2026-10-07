<!-- github-only -->
> This page is part of the mathema documentation, [read it on the site](https://mathema.tetrionlabs.com/language/reference/tutorial-trees/).
<!-- /github-only -->

# Trees

<!-- shop: threads -->

A record that holds records of its own kind is a tree: a comment and
its replies, a category and its subcategories, a folder and its files.
Trees have two things strings and flat records don't, a shape you may
want to bound, and code that walks them recursively.

## A thread

A comment is a dataclass in `shop/threads.py`, and so are the functions
on this page:

```python
@dataclass
class Comment:
    author: str
    body: str
    replies: list[Comment] = field(default_factory=list)
```

A thread, and the three numbers that describe its shape:

```text
Comment "Great mug!"                      depth 1
├── Comment "Agreed"                      depth 2
│   └── Comment "Same here"               depth 3
└── Comment "Does it fit a saucer?"       depth 2

depth 3   the most comments on any path from the top down
nodes 4   comments in the thread
width 2   the most replies any one comment has
```

Each is a refinement, like `len` for a string:
`L[shop.threads.Comment, depth <= 20]` is every thread at most twenty
comments deep, and `nodes` and `width` bound the other two the same
way. [Trees](trees.md) has the whole list and what each counts on a
JSON value rather than a record.

## The recursion limit

The shop counts a thread's comments by walking it:

```python
def thread_size(comment: Comment) -> int:
    """How many comments the thread holds, this one included."""
    return 1 + sum(thread_size(r) for r in comment.replies)
```

The obvious claim, that a thread holds at least one comment, over every
thread:

```text
for comment in L[shop.threads.Comment], thread_size(comment) >= 1
    falsified   comment = <Comment tree 1050 records deep>: raised RecursionError…
```

The arithmetic is right and the code still fails. Each reply is one more
Python call, the interpreter stops at about a thousand, and a thread a
thousand replies deep is one determined user and a loop away. Nothing
about recursion is visible in a test that builds a three-comment
thread, which is why `L[...]` for a tree always offers one past the
recursion limit.

The fix is one of two decisions again. Either the shop limits how deep
a thread may go when a reply is posted, and the claim says so with
`depth`, or `thread_size` walks the thread with a loop and a stack
instead of recursion, and the claim over every thread holds.

## A proof by induction

With the limit stated, the claim is proven, not just tested:

```text
for comment in L[shop.threads.Comment, depth <= 20], thread_size(comment) >= 1
    proven
```

mathema proves it by structural induction, the way you would on paper:
a comment with no replies has size 1, and a comment whose replies all
have size at least 1 has size at least 1 too. So the claim holds for
every thread of any shape up to depth 20, and the depth bound is what
keeps the recursion under the interpreter's limit. Induction proves
relations between two walks as well:

```python
def replies_below(comment: Comment) -> int:
    """How many replies sit under this comment, at any depth."""
    return len(comment.replies) + sum(replies_below(r) for r in comment.replies)
```

```text
for comment in L[shop.threads.Comment, depth <= 20], replies_below(comment) == thread_size(comment) - 1
    proven
```

Not every true claim about a tree has an inductive proof mathema can
find. This one compares the size with the depth, and it holds on every
thread tried without being proven:

```text
for comment in L[shop.threads.Comment, depth <= 20], thread_size(comment) >= thread_depth(comment)
    holds
```

## Where to go next

That is the tutorial. From here:

- [What to claim](catalogue.md) lists the claims worth writing for
  each kind of function;
- [Languages](languages.md), [Refinements](refinements.md) and
  [Relations and paths](paths.md) are the reference for everything
  these pages used;
- the adaptor pages say how each schema library's records become a
  language, starting with [pydantic](adaptor-pydantic.md).
