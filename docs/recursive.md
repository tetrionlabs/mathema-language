# Recursive structures

A schema that refers to itself is a language of trees. A dataclass with
`children: list[Node]`, a pydantic model or TypedDict that names itself,
and a JSON Schema whose `$ref` points back into its own document all
adapt, and so does `L[json]`, whose grammar is recursive by definition.
Members are finite and acyclic: a value that contains itself is outside
the language, and the explanation names the place the cycle closes.

```python
@dataclass
class Node:
    value: int
    children: list[Node] = field(default_factory=list)


def size(t: Node) -> int:
    return 1 + sum(size(c) for c in t.children)
```

## Depth, nodes and children

Three refinements bound a tree inside the brackets. On a record tree
they count records: `depth` is the number of records along the deepest
path (a node with no children has depth 1), `nodes` is the number of
records, and `children` is the most records any one record holds
directly. On `L[json]`, where every container is a value, they count
containers and values instead (`[[[]]]` has depth 3). Each reads `<=`,
`<`, `>=`, `>` or an interval, and they combine:

```
for t in L[myapp.Node, depth <= 10], ...
for doc in L[json, depth <= 6, children <= 50], ...
for t in L[myapp.Node, nodes in [1, 200]], ...
```

A bound the schema states itself (`maxItems` on a children list, pydantic's
`max_length`) is the language's own. Where nothing bounds a tree the
language stays unbounded, and random members are drawn within stated
sampling bounds (depth 8, 256 nodes, 16 children), which the record
names as sampling choices rather than facts about the language. For
claims about nesting, `depth(v)`, `nodes(v)`, `children(v)` and
`leaves(v)` from `mathema_language.vocabulary.tree` take any nested
dict, list, tuple or record, bound with `let`; having no schema to
read, they count every container, so a leaf record with a children
list has depth 2 there.

## What the probe visits

The hazards sit on the structure axes: the empty tree, the deepest and
the widest member the bounds allow (a refinement's own bound among
them, and one past it as the value outside the language), one long spine, and for an unbounded
language a spine past the interpreter's recursion limit, since a
recursive function over an unbounded language fails there however right
its arithmetic is. Where a library's validator recurses in Python and
stops early (the `jsonschema` validator does, pydantic does not) the
language finds that validator's limit and states it. Random draws climb
a depth ladder, 1, 2, 4 and so on up to the bound, instead of clustering
shallow, and a failing tree is shrunk inside the language by hoisting a
subtree into its parent's place, dropping a child, then shrinking the
leaves, so the witness is the smallest tree that still fails. A witness
too deep to print is summarised by its type and depth.

```
for t in L[myapp.Node], size(t) >= 1
  falsified (probe)
  witness: (<Node nested 2100 levels deep (1050 Node records)>): raised RecursionError
```

## Proof by structural induction

A claim about a recursive function over a tree language can be proven,
not only sampled, when every function it applies is a structural fold:
one `return` of arithmetic over the node's numeric fields, `len` of its
children, and `sum`, `max` or `min` of a fold over the children (with a
`default` for `max` and `min`). The derive route proves the claim for a
node with no children, then for a node with k >= 1 children assuming it
of each child, and a numeric field enters at its lower bound.

```
for t in L[myapp.Node, depth <= 20], size(t) >= 1
  proven (derive:induction)
  by structural induction over children: the base case (no children) and
  the step (k >= 1 children, the claim assumed of each) both hold, and
  depth <= 20 keeps the recursion under the interpreter's limit

for t in L[myapp.Node, depth <= 20], double_size(t) == 2 * size(t)
  proven (derive:induction)
```

The functions are recursive Python, two stack frames per level (the
call and the generator over the children), so the proof stands only
where the depth bound keeps the recursion under the interpreter's
limit, `depth <= 448` at Python's default limit of 1,000. Over an
unbounded language the mathematics is settled and the implementation is
not, the record says so, and the probe decides, which is how the
unbounded `size` claim above is falsified by a real tree.

The claims it proves: a fold against a constant (`size(t) >= 1`), two
folds related affinely by `==` (`double_size(t) == 2 * size(t)`), and two
folds related by an ordering where both aggregate with `sum`. Anything
else is declined with the reason and sampled, never disproven by the
induction, since an induction that does not go through says nothing
against the claim:

```
for t in L[myapp.Node, depth <= 20], size(t) >= 2
  falsified (probe), witness Node(value=0, children=[]): 1 vs 2
  derive: induction does not go through: the base case (no children)
  does not prove: -1 >= 0

for t in L[myapp.Node, depth <= 20], size(t) >= height(t)
  holds (probe)
  derive: two folds are related only when both aggregate by sum
```

Out of reach for now: mutual recursion between two functions, recursion
through anything but the children list, functions that carry an
accumulator, and claims that need a stronger statement than themselves
to go through (`leaves_plus(t) <= 2 * size(t)` is true and holds, but the
hypothesis as stated does not carry the step).
