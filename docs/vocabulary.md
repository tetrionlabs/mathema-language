<!-- github-only -->
> This page is part of the mathema documentation, [read it on the site](https://mathema.tetrionlabs.com/language/reference/vocabulary/).
<!-- /github-only -->

# Vocabulary

<!-- shop: text -->

Functions for use inside a claim, bound with `let` and called like any
other: `let nfkc = mathema_language.text.nfkc, for s in
L[unicode], f(nfkc(s)) == f(s)`. Each carries a stable identifier
(`text.nfkc@1`) that the record keeps, so a claim means the same thing
when another tool reads it.

## Text

In `mathema_language.text`.

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
let nfkc = mathema_language.text.nfkc, for name in L[unicode], f(nfkc(name)) == f(name)
    falsified   name = '℀': 'a/c' vs '℀'
```

## Trees

In `mathema_language.tree`, over any nested dict, list, tuple or
record. On a tree of records they count records, as the refinements
inside `L[...]` do; on plain dicts and lists they count containers and
values.

| Function | Returns |
|---|---|
| `depth(v)` | records along the deepest path, else containers; 0 for a scalar |
| `nodes(v)` | the records, else every value and container |
| `width(v)` | the most children any one node has |
| `leaves(v)` | the nodes with no children |
