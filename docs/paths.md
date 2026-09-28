# Relations and paths

<!-- shop: text formats forms -->

## `in` and `not in`

`in` holds a value to a language or a finite set, and `not in` keeps a
value out of another. Both are decided by execution, since the symbolic
lift has no reading of a language, and a missing value is a member of
nothing unless the right-hand side names it.

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

A path past the end of a list, or through a field that is not set,
reaches the missing value, which a bound admits unless it ends with
`\ {missing}`:

```text
f = first_quantity
for checkout in L[shop.forms.Checkout], checkout.cart.items[0].quantity in [7, 7] \ {missing}, f(checkout) == 7
    holds

for checkout in L[shop.forms.Checkout], checkout.cart.items[0].quantity in [7, 7], f(checkout) == 7
    falsified   (Checkout(cart=Cart(items=[]), postcode='')): 0 vs 7
```

The worked examples are on [Records and schemas](records.md).
