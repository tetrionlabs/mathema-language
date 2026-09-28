# Refinements

<!-- shop: text config threads -->

A refinement narrows a language inside its brackets: `L[unicode, len <=
32]`, `L[json, depth <= 6]`, `L[shop.threads.Comment, depth <= 50]`.
Each reads `key <= n`, `key < n`, `key >= n`, `key > n` or `key in [lo,
hi]`, and several combine with commas. A key a language cannot measure
is refused when the claim is checked, naming the keys that are known.
The probe tries the members at each bound first, then one just past it
as the value outside the language.

| Key | Measures | Applies to |
|---|---|---|
| `len` | code points, the way `len` counts | text languages |
| `depth` | nesting: records along the deepest path, or containers for `L[json]` | record trees, `L[json]` |
| `nodes` | records in all, or every value and container for `L[json]` | record trees, `L[json]` |
| `children` | the most records, items or keys one level holds | record trees, `L[json]` |

## Length

```text
f = display_name
for username in L[unicode, len <= 32], len(f(username)) <= 32
    falsified   ('aﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁ'): 33 vs 32
```

Beside the members at the bound, a length bound tries each character
whose length changes under case mapping or normalisation, repeated up to
the bound. A parameter annotated `Annotated[str, MaxLen(n)]` infers the
refinement on its own.

## Structure

On a record tree the structure keys count records, and on `L[json]` they
count the document's containers and values:

```text
f = thread_size
for comment in L[shop.threads.Comment, depth <= 20], f(comment) >= 1
    proven

f = settings_keys
for text in L[json, nodes <= 20], f(text) <= 19
    holds
```

Where nothing bounds a tree, random members are drawn within sampling
bounds the record states (depth 8, 256 nodes, 16 children), and the
hazards still reach the real extent, a spine past Python's recursion
limit included.
