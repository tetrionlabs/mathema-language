<!-- github-only -->
> This page is part of the mathema documentation, [read it on the site](https://mathema.tetrionlabs.com/language/reference/yaml/).
<!-- /github-only -->

# YAML

<!-- shop: deploy -->
<!-- requires: yaml -->
<!-- requires: ruamel -->

`L[yaml]` is every text that is one YAML document, read as YAML 1.2, the
current version of the spec. Membership is decided by ruamel.yaml's safe
loader, installed with `pip install "mathema-language[yaml]"`.

What makes YAML worth a language of its own is the gap between what
someone writes and what a loader returns. PyYAML, the loader most Python
code uses, reads by the older YAML 1.1 rules, and several plain-looking
values change meaning there:

| Written | YAML 1.2 (`L[yaml]`) | PyYAML (`yaml.safe_load`) |
|---|---|---|
| `country: no` | `'no'` | `False` |
| `on: push` | key `'on'` | key `True` |
| `mode: 012` | `12` | `10` |
| `t: 1:20` | `'1:20'` | `80` |
| `x: 1e3` | `1000.0` | `'1e3'` |
| `python: 3.10` | `3.1` | `3.1` |
| `released: 2026-10-10` | a `date` | a `date` |

These are the language's hazards, visited before any random document,
with the others a config file meets in practice: a comment after a
value, a byte-order mark, Windows line endings, an empty document,
deep nesting. Outside the language are the texts no YAML reader accepts:
a tab in the indentation, a key given twice, `a: b: c`, an unclosed
bracket, two documents in one text.

## A worked claim

The shop's deploy tool reads its configuration with PyYAML, from
`examples/shop/deploy.py`:

```python
def read_config(text: str) -> object:
    """A deploy configuration as the deploy tool reads it."""
    return yaml.safe_load(text)


def replicas(text: str) -> int:
    """How many copies of the service a configuration asks for, 1 when
    it does not say."""
    return int(yaml.safe_load(text).get("replicas", 1))
```

Comparing the tool's reading with YAML 1.2's, wherever the tool reads
the text at all:

```text
f = read_config
let reference = mathema_language.text.yaml_language.load, for text in L[yaml], assuming is_defined(f), f(text) == reference(text)
    falsified   text = '1:0': 60 vs '1:0'
```

`1:0` is the text `'1:0'` in YAML 1.2, and sixty to PyYAML, which reads
it as a base-sixty number; the same holds for a time written `1:20`. A
deploy tool reading `country: no` gets `False` the same way.

A loader that assumes a mapping fails on documents that are not one:

```text
f = replicas
for text in L[yaml], is_language_defined(text)
    falsified   text = '' (inside L[yaml]) raised AttributeError…
```

An empty file is a YAML document, and it loads as `None`, which has no
`.get`.
