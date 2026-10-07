# Relations and paths

<!-- shop: text formats forms -->

## `in` and `not in`

`in` holds a value to a language or a finite set, and `not in` keeps a
value out of another. Both are decided by execution, since the symbolic
lift has no reading of a language, and an absent value or a hole is a
member of nothing unless the right-hand side names it.

| Spelling | Reads |
|---|---|
| `f(s) in L[slug]` | every output is a slug |
| `f(s) in {"billing", "alerts"}` | every output is one of these |
| `"<" not in f(s)` | the output never contains `<` |
| `f(x) in [0, 1]` | the same as `0 <= f(x) <= 1` |

`∈` and `∉` are accepted on input and rendered in the unicode form.

```text
f = render_quantity
for n in N, f(n) in L[digit]
    holds

f = render_comment
for body in L[unicode], "<" not in f(body)
    holds
```

## Paths into a record

A binding can name a path into a member and narrow the members the
claim covers: `.field` for a field, `[0]` for an item, `[*]` for every
item, at any depth, `checkout.cart.items[*].quantity`. The derive route
reads a numeric leaf at the end of a path with the bound the schema
states for it, and a binding in the claim overrides that bound.

A bound on a path means the value is there. Where a path reaches
nothing, it reaches one of two kinds of nothing:

| The path reaches | Kind | Spelled |
|---|---|---|
| a field holding `None`, a key that is not there, an index past the end | absent | `absent` (`None` is accepted) |
| a list slot holding `None`, a NaN | a hole | `missing` (`null`, `nan` name one member) |

A record whose path is absent is outside a bare bound, and `| {absent}`
keeps it in:

```text
f = first_quantity
for checkout in L[shop.forms.Checkout], checkout.cart.items[0].quantity in [7, 7], f(checkout) == 7
    holds

for checkout in L[shop.forms.Checkout], checkout.cart.items[0].quantity in [7, 7] | {absent}, f(checkout) == 7
    falsified   checkout = Checkout(cart=Cart(items=[]), postcode=''): 0 vs 7
```

The worked examples are on [Records and schemas](records.md).
