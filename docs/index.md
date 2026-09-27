# Languages

A language is the set of values a name in a claim stands for, written
`L[ascii]` or `L[json]` where a numeric claim writes `R` or `[0, 1]`.
mathema parses, renders and records the domain; this package supplies
the names, the hazards every probe visits first, and the generators
that reach the members a fixed pool never would. The grammar itself,
and what a record states about a language, is on
[mathema's language page](https://mathema.tetrionlabs.com/language/).

## The text languages

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
functions are [the catalogue's](catalogue.md)):

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
before any random member is drawn. The hazards count toward the trial
budget the way a wide interval does, so a claim over a language gets
more trials and a confidence score marked down for the cases it has to
cover, and a language whose hazards still outnumber the budget raises
the trial count to the number of hazards, which the record's sampling
line states. The record also states which language each name resolved
to and where it came from.

## Writing your own

A language is any object satisfying `mathema.languages.Language`, and
`TextLanguage` here assembles one from a per-character test or a
whole-string predicate, a character pool, the Unicode categories random
members draw from, and the simplest character shrinking prefers. Register
it in the process with `register_language`, under a `mathema.languages`
entry point in your own package, or refer to it by its dotted path,
`L[myapp.text.SLUG]`.
