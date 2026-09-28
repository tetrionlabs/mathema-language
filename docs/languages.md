# Languages

Every language the package supplies, what its members are, what decides
membership, and where a guide shows it in use. A string language is
decided by Python's own reading (a character test, or the standard
library's parser), never a regular expression standing in for a parser.
Every language visits its hazards first: the empty string and
whitespace, control and format characters, lone surrogates, combining
marks, characters that change length under case mapping or
normalisation, homoglyphs, non-standard spaces, overlong inputs and
text that spells a missing value, plus the hazards particular to it.
Records and trees are languages too, named by the schema that describes
them; they are on [Records and schemas](records.md) and [Trees](trees.md).

## Alphabets

Every string over a set of characters, the empty string included;
`L[ascii] \ {""}` leaves it out.

| Language | Members | Decided by | Guide |
|---|---|---|---|
| `L[unicode]` | every `str`, lone surrogates included | nothing to decide | [Text](text.md) |
| `L[ascii]` | the 128 ASCII code points | `ord(c) < 128` | [Text](text.md) |
| `L[latin-1]` | what the latin-1 codec encodes | `ord(c) < 256` | [Text](text.md) |
| `L[printable]` | what Python calls printable | `str.isprintable` | [Text](text.md) |
| `L[digit]` | the ten ASCII digits | `c in "0123456789"` | [Formats](formats.md) |
| `L[alpha]` | letters in any script | `str.isalpha` | [Formats](formats.md) |
| `L[alnum]` | letters and digits in any script | `str.isalnum` | [Formats](formats.md) |

## Hazard alphabets

The characters parsers tend to get wrong, each a language of its own so
a claim can quantify over exactly them.

| Language | Members | Why it matters |
|---|---|---|
| `L[control]` | the C0 control characters and the space | newlines and NULs that end a header or a record |
| `L[invisible]` | zero-width, byte-order and bidirectional marks | text that shows nothing or reorders itself |
| `L[combining]` | combining marks | accents stacked on a letter, more code points than a reader sees |
| `L[surrogate]` | lone surrogates | a `str` Python holds and no encoding can write |
| `L[compatibility]` | characters NFKC maps to something else | ligatures, fullwidth letters, `℀` |
| `L[astral]` | characters past the basic multilingual plane | emoji, two UTF-16 units each |

## Formats

Exactly what the standard library's parser accepts on the running
Python.

| Language | Members | Decided by | Guide |
|---|---|---|---|
| `L[identifier]` | Python identifiers | `str.isidentifier` | [Formats](formats.md) |
| `L[json]` | what `json.loads` accepts, the bare `NaN` included | `json.loads` | [JSON](json.md) |
| `L[uuid]` | every spelling `uuid.UUID` reads | `uuid.UUID` | [Formats](formats.md) |
| `L[iso_date]` | ISO 8601 dates | `date.fromisoformat` | [Formats](formats.md) |
| `L[iso_datetime]` | ISO 8601 date-times | `datetime.fromisoformat` | [Formats](formats.md) |
| `L[ipv4]`, `L[ipv6]` | IP addresses | `ipaddress` | [Formats](formats.md) |
| `L[base64]` | canonical base64 | `b64decode(validate=True)`, re-encoded equal | [Formats](formats.md) |
| `L[hex]` | what `bytes.fromhex` reads | `bytes.fromhex` | [Formats](formats.md) |
| `L[slug]` | lower-case words joined by single hyphens | `[a-z0-9]+(-[a-z0-9]+)*` | [Formats](formats.md) |
| `L[shell_safe]` | a word the shell reads literally | `shlex.quote(s) == s` | [Formats](formats.md) |

`L[iso_date]` and `L[iso_datetime]` follow the running Python, which
reads more ISO 8601 forms from 3.11 on, so the same claim can cover
more spellings there.

## Combining languages

A domain can join languages and finite sets, and leave values out:

```text
for s in L[ascii] \ {""}, ...            every non-empty ASCII string
for s in L[slug] | {"-"}, ...            a slug, or the placeholder "-"
for s in L[unicode, len <= 80], ...      at most eighty code points
```

A language of your own is named the same way, by its dotted path:
[Writing a language](writing-a-language.md).
