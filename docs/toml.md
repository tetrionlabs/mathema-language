<!-- github-only -->
> This page is part of the mathema documentation, [read it on the site](https://mathema.tetrionlabs.com/language/reference/toml/).
<!-- /github-only -->

# TOML

<!-- shop: settings -->
<!-- requires-python: 3.11 -->

`L[toml]` is every text that is one TOML 1.0 document. Membership is
decided by the standard library's `tomllib`, so nothing extra is needed
on Python 3.11 and later; on 3.10, `pip install "mathema-language[toml]"`
brings `tomli`, the same reader under its earlier name.

TOML has one reading, unlike YAML, so the gap worth a language is
between what a reader returns and what the code handling it expects.
Several plain-looking values come back as something other than text,
a number or a table:

| Written | Read as |
|---|---|
| `released = 2026-10-10` | a `datetime.date`, which `json.dumps` refuses |
| `at = 2026-10-10T09:00:00` | a `datetime` with no time zone |
| `opens = 09:00:00` | a `datetime.time` |
| `version = 3.10` | the float `3.1` |
| `limit = inf`, `ratio = nan` | floats that JSON has no spelling for |
| `id = 99999999999999999999` | a Python `int`, refused by readers in other languages |
| `server.host = "db"` | `{'server': {'host': 'db'}}` |
| `"a.b" = 1` | `{'a.b': 1}`, a key containing a dot |
| `[[items]]` | a list of tables |

These are the language's hazards, visited before any random document,
with the others a config file meets in practice: underscores and octal
in integers, a literal string where a backslash stays a backslash, a
multi-line string whose first line break is dropped, Windows line
endings, an empty document. Outside the language are the texts no TOML
reader accepts: a key or a table given twice, a value with a leading
zero, a bare word as a value, a trailing comma or a line break inside
an inline table, a date that does not exist, a byte-order mark.

## A worked claim

The shop's status page shows the service settings as JSON, from
`examples/shop/settings.py`:

```python
def settings_json(text: str) -> str:
    """The settings a TOML file gives, as the JSON the status page
    shows."""
    return json.dumps(tomllib.loads(text))
```

Claiming every settings file gets a page:

```text
f = settings_json
for text in L[toml], is_language_defined(text)
    falsified   text = 'a=0006-10-10' (inside L[toml]) raised TypeError…
```

A date is a valid setting, and `json.dumps` has no spelling for a
`datetime.date`, so the page fails for any settings file that records
when something was released. The witness is shrunk to the shortest
document that still fails; the first hazard, `released = 2026-10-10`,
fails the same way.
