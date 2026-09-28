# Vocabulary

<!-- shop: text -->

Functions for use inside a claim, bound with `let` and called like any
other: `let nfkc = mathema_language.vocabulary.text.nfkc, for s in
L[unicode], f(nfkc(s)) == f(s)`. Each carries a stable identifier
(`text.nfkc@1`) that the record keeps, so a claim means the same thing
when another tool reads it.

## Text

In `mathema_language.vocabulary.text`.

| Function | Returns |
|---|---|
| `nfc(s)`, `nfd(s)` | the canonical composed or decomposed form |
| `nfkc(s)`, `nfkd(s)` | the compatibility forms: ligatures, fullwidth letters, `℀` folded |
| `casefold(s)`, `lower(s)`, `upper(s)` | the full Unicode case mappings |
| `count(s, part)` | how many times `part` occurs |
| `startswith(s, prefix)`, `endswith(s, suffix)` | whether `s` begins or ends with it |
| `strip(s)` | leading and trailing whitespace removed |
| `splitlines(s)` | the lines, on every Unicode line boundary |
| `nfc_len(s)` | the length in NFC code points |
| `utf8_len(s)` | the length in UTF-8 bytes, what a byte-limited field counts |

```text
f = username_key
let nfkc = mathema_language.vocabulary.text.nfkc, for name in L[unicode], f(nfkc(name)) == f(name)
    falsified   ('℀'): 'a/c' vs '℀'
```

## Trees

In `mathema_language.vocabulary.tree`, over any nested dict, list, tuple
or record. With no schema to read they count every container, so a
record holding a list of children is two levels, where a refinement on a
record language counts one.

| Function | Returns |
|---|---|
| `depth(v)` | nesting levels, 0 for a scalar |
| `nodes(v)` | every value and container |
| `children(v)` | the most direct children one container has |
| `leaves(v)` | the values with no children |
