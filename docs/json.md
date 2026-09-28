# JSON

<!-- shop: config -->

`L[json]` is every document Python's JSON parser accepts, which is more
than the JSON standard: a bare `NaN`, `Infinity` and `-Infinity` are
members, since a function reading JSON with `json.loads` will be handed
them, and a function that breaks on them is falsified rather than the
language narrowed. The probe tries JSON's own hazards first: a number
past the largest double, the bare `NaN`, an escaped lone surrogate,
fifty nested arrays, and documents nested past Python's recursion limit
that the parser still accepts.

The examples are the shop's settings files, from
`examples/shop/config.py`.

## Nesting

Code that walks a parsed document recursively stops at Python's
recursion limit, a thousand frames, while the parser accepts documents
nested almost ten thousand deep:

```python
def settings_keys(text: str) -> int:
    """How many keys a settings document holds, at every level."""
    return _keys(json.loads(text))
```

```text
f = settings_keys
for text in L[json], f(text) >= 0
    falsified

for text in L[json, depth <= 100], f(text) >= 0
    holds
```

The first is falsified by a document nested past the recursion limit,
which raises `RecursionError`; the second states the depth the service
accepts and holds. Three refinements bound a document inside the
brackets, counted over the document's values and containers:

| Refinement | Counts | A document at 3 |
|---|---|---|
| `depth` | containers along the deepest path | `[[[]]]` |
| `nodes` | every value and container | `{"a": 0, "b": 0}` |
| `children` | the most items or keys one container holds | `[0, 0, 0]` |

Each reads `<=`, `<`, `>=`, `>` or an interval, `in [1, 50]`, and they
combine: `L[json, depth <= 6, children <= 100]`. The probe tries the
document at each bound, as an array and as an object, and one just past
it:

```text
f = settings_keys
for text in L[json, nodes <= 20], f(text) <= 9
    falsified   ('{" ":0,"1":0,"a":0,"k":0,"3":0,"":0,"5":0,"6":0,"7":0,"8":0}'): 10 vs 9

for text in L[json, nodes <= 20], f(text) <= 19
    holds
```

## Round trips and the bare NaN

Reading a document and writing it back is the most common JSON
operation, and the claim that it loses nothing is stated over the
parsed values, with `json.loads` bound in the claim:

```python
def resave(text: str) -> str:
    """A settings document written back out after it is read."""
    return json.dumps(json.loads(text))
```

```text
f = resave
let loads = json.loads, for text in L[json, depth <= 100], loads(f(text)) == loads(text)
    falsified   ('NaN'): loads returned nan
```

A bare `NaN` parses to a float NaN, and a NaN is no value and equal to
nothing, itself included, so the round trip cannot be shown to preserve
it. A service that must never store one says so by rejecting it on the
way in.

## Recipes

| To say | Write |
|---|---|
| it handles any document the parser accepts | `for s in L[json], is_arbitrary_input_safe(s)` |
| it handles documents up to the depth you accept | `for s in L[json, depth <= 100], ...` |
| reading and writing loses nothing | `let loads = json.loads, for s in L[json], loads(f(s)) == loads(s)` |
| formatting twice is formatting once | `for s in L[json], f(f(s)) == f(s)` |
