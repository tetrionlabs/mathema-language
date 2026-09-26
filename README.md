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

with:     falsified  ('\u00df'): raised UnicodeEncodeError

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
an alphabet boundary: `\u00df` is latin-1 and not ascii, and the function
that encodes as ascii is falsified with it as the witness, while over
`L[ascii]` the probe never leaves the language and the claim holds.

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
regular expression crawl. The record states which language each name
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

0.1.0. Text languages and the hazard corpus; the hazard families over
text and the schema languages of rows follow.
