# Writing a language

<!-- shop: skus -->

A format of your own is a language of your own, and a claim names it by
its dotted path, `L[shop.skus.SKU]`, with nothing to register.
`TextLanguage` assembles one from a test for a whole string (`accepts`)
or for each character (`char_ok`), a generator for members a pool of
characters would rarely reach, and characters that lie outside it for
the near non-members:

```python
SKU = TextLanguage(
    "sku", level="predicate",
    accepts=lambda s: re.fullmatch(r"[A-Z]{3}-[0-9]{4}", s) is not None,
    generate=lambda rng: "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(3))
    + "-" + "".join(rng.choice("0123456789") for _ in range(4)),
    outside_pool="a-_ ")


def parse_sku(text: str) -> tuple:
    """A SKU split into its product line and item number."""
    line, number = text.split("-")
    return line, int(number)


def format_sku(parts: tuple) -> str:
    """A product line and item number written as a SKU."""
    line, number = parts
    return f"{line}-{number:04d}"


def normalise_sku(text: str) -> str:
    """A SKU typed by a person, as the stock system stores it."""
    return text.strip().upper()
```

```text
f = normalise_sku
for text in L[shop.skus.SKU], f(text) in L[shop.skus.SKU]
    holds

f = parse_sku
let fmt = shop.skus.format_sku, for text in L[shop.skus.SKU], fmt(f(text)) == text
    holds

for text in L[shop.skus.SKU], excluded_outside_domain(text)
    falsified   text = '-1' (outside L[shop.skus.SKU]: sku)
```

The parser accepts `'-1'`, which is not a SKU, because it only splits on
the hyphen. A language gets the text hazards for free, and
`extra_hazards` adds its own.

Other ways to make a language resolvable: `register_language("sku",
SKU)` in the process that checks the claims, which makes `L[sku]`
work, or an entry point under `mathema.languages` in your package's
metadata, which makes it work wherever your package is installed. Any
object that satisfies mathema's `Language` protocol is a language;
`TextLanguage` is the kit for text, and an adaptor is the way to make a
schema library's classes languages, on [Writing an adaptor](adaptors.md).
