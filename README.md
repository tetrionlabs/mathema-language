# mathema-language

The languages a mathema claim quantifies text over.

mathema checks claims about code, and a claim about a function of text
needs a domain the way a claim about a function of numbers does, namely
a language: the set of strings a name stands for, written `L[ascii]` or
`L[json]` where a numeric claim writes `R` or `[0, 1]`. mathema itself
parses, renders and records that domain and resolves no name, so on its
own a claim over `L[unicode]` is not wrong, only unresolved. This package
supplies the names, with Python's own reading of each alphabet or parser
as the membership test, the hazard strings real code mishandles as the
first members every probe visits, and a generator that reaches the
astral planes and the character categories a fixed pool never would.

## Install

```
pip install mathema-language
```

mathema discovers it through the `mathema.languages` entry point once
installed; there is nothing to configure.

## Before and after

```
claim: for s in L[unicode], len(f(s)) == len(s)        f = str.upper

without:  skipped    unknown language L[unicode]: known languages are none in
                     this process; a package adds one under the
                     'mathema.languages' entry-point group, and
                     'pip install "mathema[language]"' brings the built-in
                     alphabets and languages
with:     falsified  ('\u0390'): 3 vs 1

claim: for s in L[latin-1], f(s) == s                   f = ascii_only

with:     falsified  ('\u00ff'): raised UnicodeEncodeError

claim: for s in L[ascii], f(s) == s                     f = ascii_only

with:     holds      n=128
```

The falsifications are the point. Upper-casing looks like it keeps a
string's length and does not over the whole of Unicode, because `\u0390`
(iota with dialytika and tonos) upper-cases to three code points and
`\u00df` to two, and a probe that never draws those characters would
report `holds` for a claim that is false; the hazard corpus here is
built from what the test suites of Django, Werkzeug, MarkupSafe, ftfy and
CPython found the hard way, so those characters are among the first
strings tried, not a lucky draw. The second claim is the same lesson at
an alphabet boundary: `\u00ff` (y with diaeresis) is latin-1 and not
ascii, and the function that encodes as ascii is falsified with it as
the witness, while over `L[ascii]` the probe never leaves the language
and the claim holds.

## The languages

Every alphabet language is every string over its characters, the empty
string included, the way a Kleene star reads; `L[ascii] \ {""}` is the
spelling that excludes it. Every predicate language is exactly what its
standard-library parser accepts on the running Python, and nothing here
re-implements a parser as a regular expression.

| Name | Members | Membership test |
|---|---|---|
| `unicode` | every `str`, lone surrogates included | none needed |
| `ascii` | strings over the 128 ascii code points | `ord(c) < 128` |
| `latin-1` | what the latin-1 codec encodes | `ord(c) < 256` |
| `printable` | what `str.isprintable` accepts | `str.isprintable` |
| `digit` | strings over the ten ascii digits | `c in "0123456789"` |
| `alpha`, `alnum` | letters, and letters with digits, any script | `str.isalpha`, `str.isalnum` |
| `identifier` | Python identifiers | `str.isidentifier` |
| `json` | JSON documents | `json.loads` |
| `uuid` | every spelling `uuid.UUID` reads, braces and urns included | `uuid.UUID` |
| `iso_date`, `iso_datetime` | what `fromisoformat` accepts | `date.fromisoformat`, `datetime.fromisoformat` |
| `ipv4`, `ipv6` | addresses | `ipaddress.IPv4Address`, `ipaddress.IPv6Address` |
| `base64` | canonical base64 | `b64decode(validate=True)` and back |
| `hex` | what `bytes.fromhex` accepts | `bytes.fromhex` |
| `slug` | lower-case words joined by single hyphens | `[a-z0-9]+(-[a-z0-9]+)*` |
| `shell_safe` | a non-empty word a shell reads literally | `shlex.quote(s) == s` |

The hazard sub-alphabets are languages of their own, so a claim can
quantify over exactly the characters a parser tends to get wrong: `c0`
(the control code points and the space), `format` (zero-width joiners
and spaces, the byte-order mark, the bidirectional controls, the tag
characters), `combining` (the combining marks), `surrogate` (the
surrogate code points Python admits and no codec encodes),
`nfkc_folding` (the characters whose NFKC form differs, ligatures and
fullwidth forms among them) and `non_bmp` (everything past the basic
multilingual plane).

## Closure, containment and length

A claim can hold an output to a language, or keep a token out of it,
with the `in` relation, and it reads the way it is written (the
functions are the catalogue's, below):

```
for s in L[unicode], f(s) in L[slug]          f = slugify
for s in L[unicode], "<" not in f(s)           f = escape_html
for n in N, f(n) in L[digit]                   f = render_count
```

The first is closure into a language other than the input's own, and it
is falsified by any input with no ASCII letter or digit in it, which
slugifies to the empty string, and the empty string is not a slug; the
second is containment, and holds, since no angle bracket survives the
escape; the third holds, every count spelling in the ten ASCII digits.
Membership is decided by execution, since the symbolic lift has no
reading of a language, and a missing value is a member of nothing.
`output_in_language(f(s))` stays as the short form of closure into the
input's own language, and its record names the language it held the
output to and where that came from, under
`meta["mathema.language"]["return"]`.

A language can carry a bound on length, counted in code points the way
Python's `len` counts: `L[ascii, len <= 80]`,
`L[unicode, len in [1, 64]]`, `L[slug, len >= 3]`. The members at the
bounds are among the first values a probe tries, and the member one past
the bound is the outside draw `excluded_outside_domain` uses, so a
function that truncates at seventy-nine is caught at eighty. A parameter
annotated `Annotated[str, MaxLen(80)]` infers `L[unicode, len <= 80]` on
its own, with the inference stated in the record's note, and in a claim
that writes an `L[...]` domain `len(s)` renders as `len(s)` rather than
as mathema's canonical `dim(s, 0)`.

## What to claim

The nature of a function over text (parser, renderer, normaliser,
validator, escaper, consumer) says which claims are worth writing before
you have read the body, and [the catalogue](docs/catalogue.md) lists them
by nature with a real function under each, every row run by the test
suite and held to the verdict printed beside it.

## Rows

A schema is a language too. `L[myapp.models.Order]` names the records of
a dataclass, a TypedDict, a pydantic model, a JSON Schema, a SQLAlchemy
table or a Django model, read into one neutral model by an adaptor and
validated by the library's own validator where it has one (pydantic's,
the JSON Schema validator, an in-memory SQLite database for SQLAlchemy,
`full_clean` for Django). A parameter annotated with the class infers
the language on its own:

```
for o in L[myapp.models.Order], f(o) >= 0
```

The probe visits one record per field hazard first (the extremes, the
text corpus in a string column, the longest string a column allows, the
datetime64[ns] bounds and a DST edge), and a witness names the field in
one path grammar for every ecosystem, `.qty` for a column and
`.ship.city` for a nested one.

A row can be proven, not only sampled. Where the body reads only numeric
fields, and text fields only through `len`, the derive route lifts each
field the body reads to a symbol bounded by the schema, a quantity
annotated `Ge(1), Le(10)` as a whole number from one to ten, a price
annotated `Ge(0.0)` as a real at least zero, `len(o.sku)` on a field
annotated `MaxLen(8)` as a whole number from nought to eight, so
`for o in L[Order], f(o) >= 0` over `o.qty * o.price` is proven, and the
fields the body never reads (a note, a list of tags) do not stand in the
way. Where the body reads a field the lift has no reading of, a
`Literal` compared against a string, say, the lift declines, the note
names the field, and the claim is sampled instead.

## What a probe visits

A language's hazards come first, then random members, and never a value
outside the language: the empty string and whitespace, NUL and the
other control code points, the byte-order mark and the bidirectional
override, lone and paired surrogates, combining sequences that render as
fewer characters than they hold, the characters whose case mapping or
NFKC form changes their length, tag-sequence flags and joiner emoji, a
Cyrillic homoglyph of `a`, no-break spaces, a string past the largest
double, the text that spells `null` or `NA`, the entity that is escaped
three times over, and the overlong inputs that make a backtracking
regular expression crawl. Every hazard of the language is visited once
before any random member is drawn, however small a trial budget the
function would otherwise get. The record states which language each name
resolved to and where it came from.

## Writing your own

A language is any object satisfying `mathema.languages.Language`, and
`TextLanguage` here assembles one from a per-character test or a
whole-string predicate, a character pool, the Unicode categories random
members draw from, and the simplest character shrinking prefers. Register
it in the process with `register_language`, under a `mathema.languages`
entry point in your own package, or refer to it by its dotted path,
`L[myapp.text.SLUG]`.

## Requirements

Python 3.10 or later and mathema. The package imports only from
`mathema.interfaces.extension`, the surface mathema versions for
extension authors, and a test pins that.

## Licence

Apache-2.0. mathema itself is licensed separately.

## Version

0.1.0. Text languages and the hazard corpus, the hazard families over
text, and the schema languages of rows.
