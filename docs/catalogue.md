<!-- github-only -->
> This page is part of the mathema documentation, [read it on the site](https://mathema.tetrionlabs.com/language/reference/catalogue/).
<!-- /github-only -->

# What to claim about a function over text

A function over text has one of a few natures, and the nature says which
claims are worth writing before you have read a line of the body. Every
claim below runs as written: the test suite executes this page and holds
each row to the verdict printed beside it, so a row that says `falsified`
is a real finding about the function above it, not a hypothetical. The
domain binding is always the input side (`for s in L[ascii]` says what
the function is fed), and anything said about `f(...)` is the output side.

The rows use three kinds of claim. A hazard family (`is_length_safe`,
`is_encoding_safe`, `is_language_defined`, `excluded_outside_domain`)
feeds the function the language's own hazards and reports an unguarded
crash or a missing rejection. A law (`f(f(s)) == f(s)`,
`len(f(s)) <= len(s)`) is adjudicated by derive where the body lifts
and by sampling where it does not, sampling never proving. Membership,
`f(s) in L[slug]` or `"<" not in f(s)`, holds every output to a language
of your choosing or keeps a token out of it, which is what closure and
containment mean for a normaliser or an escaper, and is decided by
execution, since the symbolic lift has no reading of a language.


A language can carry a length bound, `L[unicode, len <= 80]`, the
members of the language no longer than eighty code points, and a
parameter annotated `Annotated[str, MaxLen(80)]` infers exactly that
language with no binding written. The members at the bound are among
the first values the probe tries, so a function that is only right up
to a length one short of the bound is caught at the bound, not by luck.

## Parser

A parser takes text and returns a value or refuses. The claims that
matter are that it refuses what is outside its language, that no hazard
crashes it, and that it is a section of its renderer where that is
intended.

```python
def parse_count(s: str) -> int:
    """The count a decimal string spells."""
    return int(s)


def render_count(n: int) -> str:
    """The decimal spelling of a count."""
    return str(n)
```

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `parse_count` | `for s in L[digit], excluded_outside_domain(s)` | falsified | `int` accepts more than the ten ASCII digits: surrounding whitespace, underscores, and every Unicode decimal digit, so an outside draw is parsed rather than refused. |
| `parse_count` | `for s in L[digit], is_encoding_safe(s)` | unknown | The ten ASCII digits hold no control or encoding hazard, so the family has nothing to try and says so rather than reporting a hollow `holds`. Claim it over what the parser is really fed. |
| `parse_count` | `for s in L[unicode], is_encoding_safe(s)` | holds | Every non-digit is refused with a `ValueError`, a declared rejection, never a `UnicodeError`. |
| `parse_count` | `for s in L[digit], is_length_safe(s)` | holds | A sixty-four kibibyte digit string is refused by the interpreter's own digit limit, a `ValueError` again. |
| `parse_count` | `for s in L[digit] \ {""}, render_count(f(s)) == s` | falsified | Leading zeros do not survive the round trip: `"007"` parses to `7`, which renders as `"7"`. |

## Renderer

A renderer takes a value and returns text. Its claims are about the text
it produces: non-empty, inside the language it promises, and inverted by
the matching parser.

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `render_count` | `for n in N, len(f(n)) >= 1` | holds | Every count spells as at least one digit. |
| `render_count` | `for n in N, parse_count(f(n)) == n` | holds | The parser inverts the renderer on the renderer's own output, which is the direction that does hold. |
| `render_count` | `for n in N, f(n) in L[digit]` | holds | The sharp form: every count spells in the ten ASCII digits and nothing else. |

## Normaliser

A normaliser maps text to text and is meant to settle: applying it twice
is applying it once, it never lengthens its input, and it commutes with
Unicode normalisation when it claims to work on characters rather than
code points. Case mapping is the classic place the last of those fails.

```python
import re
from typing import Annotated

from annotated_types import MaxLen


def collapse_spaces(s: str) -> str:
    """Whitespace runs collapsed to one space, the ends stripped."""
    return " ".join(s.split())


def shout(s: str) -> str:
    """Upper case."""
    return s.upper()


def slugify(s: str) -> str:
    """The lower-case ASCII words of s, joined by hyphens."""
    return "-".join(re.findall(r"[a-z0-9]+", s.lower()))


def headline(s: str) -> str:
    """At most eighty characters of s."""
    return s[:80]


def label(s: Annotated[str, MaxLen(80)]) -> str:
    """The label, cut to the eighty characters it is declared to fit."""
    return s[:80]
```

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `collapse_spaces` | `for s in L[unicode], f(f(s)) == f(s)` | holds | Idempotent: a second pass finds nothing to collapse. |
| `collapse_spaces` | `for s in L[unicode], len(f(s)) <= len(s)` | holds | A contraction, since it only ever removes characters. |
| `collapse_spaces` | `for s in L[ascii], f(s) in L[ascii]` | holds | Closure: ASCII in, ASCII out. |
| `collapse_spaces` | `for s in L[ascii], f(s) in L[ascii]` | holds | The same closure written as membership, which is the spelling to reach for when the target is not the input's own language. |
| `collapse_spaces` | `for s in L[unicode], "  " not in f(s)` | holds | No two spaces survive in a row, which is the whole job of the function stated as a containment. |
| `collapse_spaces` | `let n = mathema_language.text.nfc, for s in L[unicode], n(f(s)) == f(n(s))` | holds | Commutes with NFC, because composition never creates or removes whitespace. |
| `collapse_spaces` | `for s in L[unicode], f(s) == s` | falsified | Not the identity; the first whitespace hazard is the witness. |
| `shout` | `for s in L[ascii], len(f(s)) == len(s)` | holds | Over ASCII, upper-casing is one character to one character. |
| `shout` | `for s in L[unicode], len(f(s)) == len(s)` | falsified | `'ΐ'` (U+0390) upper-cases to three code points, and `'ß'` to two; a length-preserving assumption about case mapping is the bug this row exists to catch. |
| `slugify` | `for s in L[unicode], len(f(s)) <= len(s)` | holds | Only ever keeps characters it was given and puts one hyphen between words it kept. |
| `slugify` | `for s in L[unicode], f(s) in L[slug]` | falsified | The empty string, and any string with no ASCII letter or digit in it, slugifies to the empty string, which is not a slug; a caller that stores the result as a key needs to know. |
| `headline` | `for s in L[unicode], len(f(s)) <= 80` | holds | The cut is the bound. |
| `headline` | `for s in L[unicode, len <= 80], f(s) == s` | holds | Inside the bound the cut changes nothing. |
| `headline` | `for s in L[unicode, len <= 81], f(s) == s` | falsified | One past it, the member of length 81 at the bound loses its last character. |
| `label` | `f(s) == s` | holds | No binding written: `MaxLen(80)` on the parameter infers `L[unicode, len <= 80]`, and the record says so. |

## Validator

A validator maps text to a truth value. Its claims are that it agrees
with the language it stands for and that nothing in the language, however
long or strange, crashes it; a backtracking regular expression is the
usual way a validator fails the second of those.

```python
import re


def is_slug(s: str) -> bool:
    """Whether `s` is a slug: lower-case words joined by single hyphens."""
    return re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", s) is not None
```

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `is_slug` | `for s in L[slug], f(s) == True` | holds | Every member of `L[slug]` is accepted. |
| `is_slug` | `for s in L[slug], is_length_safe(s)` | holds | The pattern is linear in the input, so the long and pathological members return promptly. |
| `is_slug` | `for s in L[unicode], is_language_defined(s)` | holds | A `fullmatch` never raises on a `str`, whatever it holds. |

## Escaper

An escaper maps text into a sub-language and is inverted by its
unescaper. The claims are the round trip, the growth bound, closure into
the target alphabet, and (the one that usually fails) that escaping is
not idempotent, which is exactly why double escaping is a bug.

```python
import html


def escape_html(s: str) -> str:
    """The s with `&`, `<`, `>` and both quotes as entities."""
    return html.escape(s)
```

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `escape_html` | `for s in L[unicode], len(f(s)) >= len(s)` | holds | Every replacement is longer than the character it replaces. |
| `escape_html` | `let u = html.unescape, for s in L[unicode], u(f(s)) == s` | holds | The round trip through `html.unescape` is exact. |
| `escape_html` | `for s in L[ascii], f(s) in L[ascii]` | holds | Entities are ASCII, so ASCII in gives ASCII out. |
| `escape_html` | `for s in L[unicode], "<" not in f(s)` | holds | No angle bracket survives, whatever the input holds, which is the claim a template relies on. |
| `escape_html` | `for s in L[unicode], "&" not in f(s)` | falsified | The ampersand is the escape character itself, so every entity puts one back; containment is the wrong claim for it, and the round trip above is the right one. |
| `escape_html` | `for s in L[unicode], is_encoding_safe(s)` | holds | No codec in the body, so no codec boundary to fall off. |
| `escape_html` | `for s in L[unicode], f(f(s)) == f(s)` | falsified | `"&"` becomes `"&amp;"` and then `"&amp;amp;"`; an escaper is not a normaliser. |

## Consumer

A consumer maps text to a number. Its claims are ordinary numeric claims
over a language, and the row that fails here is the one that assumes a
non-empty string has content.

```python
def word_count(s: str) -> int:
    """How many whitespace-separated words `s` holds."""
    return len(s.split())
```

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `word_count` | `for s in L[unicode], f(s) >= 0` | holds | A length is never negative. |
| `word_count` | `for s in L[unicode] \ {""}, f(s) >= 1` | falsified | A whitespace-only string is non-empty and has no words. |
| `word_count` | `for s in L[unicode], is_language_defined(s)` | holds | `str.split` copes with every hazard in the corpus. |

## Row

A function over one record reads fields, and a row schema says what
each field can hold, so a claim over the row's language quantifies over
every valid record. Where the body reads only numeric fields, and text
fields only through `len`, the derive route lifts each field it reads to
a symbol bounded by the schema (a quantity between one and ten, a price
at least zero, a code of at most eight characters as a whole number from
nought to eight), and the claim is proven rather than sampled; the fields
the body never reads do not stand in the way. Where the lift declines,
the note names the field it could not read, and the probe draws valid
records, hazards first.

```python
from dataclasses import dataclass
from typing import Annotated

from annotated_types import Ge, Le, MaxLen


@dataclass
class Line:
    sku: Annotated[str, MaxLen(8)]
    qty: Annotated[int, Ge(1), Le(10)]
    price: Annotated[float, Ge(0.0)]
    note: str = ""


def line_total(line: Line) -> float:
    """Quantity times price."""
    return line.qty * line.price


def line_width(line: Line) -> int:
    """The columns the sku takes, with a space either side."""
    return len(line.sku) + 2
```

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `line_total` | `for line in L[catalogue_row.Line], f(line) >= 0` | proven | The quantity is at least one and the price at least zero, so the product is at least zero; the lift reads both bounds off the annotations. |
| `line_total` | `for line in L[catalogue_row.Line], f(line) <= 50` | falsified | The price has no upper bound, and an executed record with a large price is the witness. |
| `line_width` | `for line in L[catalogue_row.Line], f(line) <= 10` | proven | `len(line.sku)` lifts as a whole number no larger than the `MaxLen(8)` on the field. |
| `line_width` | `for line in L[catalogue_row.Line], f(line) <= 9` | falsified | An eight-character sku is valid and needs ten columns. |
