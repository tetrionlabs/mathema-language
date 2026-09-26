# What to claim about a function over text

A function over text has one of a few natures, and the nature says which
claims are worth writing before you have read a line of the body. Every
claim below runs as written: the test suite executes this page and holds
each row to the verdict printed beside it, so a row that says `falsified`
is a real finding about the function above it, not a hypothetical. The
domain binding is always the input side (`for text in L[ascii]` says what
the function is fed), and anything said about `f(...)` is the output side.

The rows use three kinds of claim. A hazard family (`is_length_safe`,
`is_encoding_safe`, `is_arbitrary_input_safe`, `excluded_outside_domain`)
feeds the function the language's own hazards and reports an unguarded
crash or a missing rejection. A law (`f(f(text)) == f(text)`,
`len(f(text)) <= len(text)`) is adjudicated by derive where the body lifts
and by sampling where it does not, sampling never proving. And
`output_in_language(f(text))` holds every output to the language the input
is declared over, which is what closure means for a normaliser or an
escaper.

## Parser

A parser takes text and returns a value or refuses. The claims that
matter are that it refuses what is outside its language, that no hazard
crashes it, and that it is a section of its renderer where that is
intended.

```python
def parse_count(text: str) -> int:
    """The count a decimal string spells."""
    return int(text)


def render_count(n: int) -> str:
    """The decimal spelling of a count."""
    return str(n)
```

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `parse_count` | `for text in L[digit], excluded_outside_domain(text)` | falsified | `int` accepts more than the ten ASCII digits: surrounding whitespace, underscores, and every Unicode decimal digit, so an outside draw is parsed rather than refused. |
| `parse_count` | `for text in L[digit], is_encoding_safe(text)` | unknown | The ten ASCII digits hold no control or encoding hazard, so the family has nothing to try and says so rather than reporting a hollow `holds`. Claim it over what the parser is really fed. |
| `parse_count` | `for text in L[unicode], is_encoding_safe(text)` | holds | Every non-digit is refused with a `ValueError`, a declared rejection, never a `UnicodeError`. |
| `parse_count` | `for text in L[digit], is_length_safe(text)` | holds | A sixty-four kibibyte digit string is refused by the interpreter's own digit limit, a `ValueError` again. |
| `parse_count` | `for text in L[digit] \ {""}, render_count(f(text)) == text` | falsified | Leading zeros do not survive the round trip: `"007"` parses to `7`, which renders as `"7"`. |

## Renderer

A renderer takes a value and returns text. Its claims are about the text
it produces: non-empty, inside the language it promises, and inverted by
the matching parser.

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `render_count` | `for n in N, len(f(n)) >= 1` | holds | Every count spells as at least one digit. |
| `render_count` | `for n in N, parse_count(f(n)) == n` | holds | The parser inverts the renderer on the renderer's own output, which is the direction that does hold. |
| `render_count` | `for n in N, output_in_language(f(n))` | holds | With no text parameter declared, the target language comes from the `str` return annotation, every string, so this row is the weak form; the sharp form, `f(n) in L[digit]`, arrives with the `in` relation. |

## Normaliser

A normaliser maps text to text and is meant to settle: applying it twice
is applying it once, it never lengthens its input, and it commutes with
Unicode normalisation when it claims to work on characters rather than
code points. Case mapping is the classic place the last of those fails.

```python
def collapse_spaces(text: str) -> str:
    """Whitespace runs collapsed to one space, the ends stripped."""
    return " ".join(text.split())


def shout(text: str) -> str:
    """Upper case."""
    return text.upper()
```

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `collapse_spaces` | `for text in L[unicode], f(f(text)) == f(text)` | holds | Idempotent: a second pass finds nothing to collapse. |
| `collapse_spaces` | `for text in L[unicode], len(f(text)) <= len(text)` | holds | A contraction, since it only ever removes characters. |
| `collapse_spaces` | `for text in L[ascii], output_in_language(f(text))` | holds | Closure: ASCII in, ASCII out. |
| `collapse_spaces` | `let n = mathema_language.vocabulary.text.nfc, for text in L[unicode], n(f(text)) == f(n(text))` | holds | Commutes with NFC, because composition never creates or removes whitespace. |
| `collapse_spaces` | `for text in L[unicode], f(text) == text` | falsified | Not the identity; the first whitespace hazard is the witness. |
| `shout` | `for text in L[ascii], len(f(text)) == len(text)` | holds | Over ASCII, upper-casing is one character to one character. |
| `shout` | `for text in L[unicode], len(f(text)) == len(text)` | falsified | `'ΐ'` (U+0390) upper-cases to three code points, and `'ß'` to two; a length-preserving assumption about case mapping is the bug this row exists to catch. |

## Validator

A validator maps text to a truth value. Its claims are that it agrees
with the language it stands for and that nothing in the language, however
long or strange, crashes it; a backtracking regular expression is the
usual way a validator fails the second of those.

```python
import re


def is_slug(text: str) -> bool:
    """Whether `text` is a slug: lower-case words joined by single hyphens."""
    return re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", text) is not None
```

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `is_slug` | `for text in L[slug], f(text) == True` | holds | Every member of `L[slug]` is accepted. |
| `is_slug` | `for text in L[slug], is_length_safe(text)` | holds | The pattern is linear in the input, so the long and pathological members return promptly. |
| `is_slug` | `for text in L[unicode], is_arbitrary_input_safe(text)` | holds | A `fullmatch` never raises on a `str`, whatever it holds. |

## Escaper

An escaper maps text into a sub-language and is inverted by its
unescaper. The claims are the round trip, the growth bound, closure into
the target alphabet, and (the one that usually fails) that escaping is
not idempotent, which is exactly why double escaping is a bug.

```python
import html


def escape_html(text: str) -> str:
    """The text with `&`, `<`, `>` and both quotes as entities."""
    return html.escape(text)
```

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `escape_html` | `for text in L[unicode], len(f(text)) >= len(text)` | holds | Every replacement is longer than the character it replaces. |
| `escape_html` | `let u = html.unescape, for text in L[unicode], u(f(text)) == text` | holds | The round trip through `html.unescape` is exact. |
| `escape_html` | `for text in L[ascii], output_in_language(f(text))` | holds | Entities are ASCII, so ASCII in gives ASCII out. |
| `escape_html` | `for text in L[unicode], is_encoding_safe(text)` | holds | No codec in the body, so no codec boundary to fall off. |
| `escape_html` | `for text in L[unicode], f(f(text)) == f(text)` | falsified | `"&"` becomes `"&amp;"` and then `"&amp;amp;"`; an escaper is not a normaliser. |

## Consumer

A consumer maps text to a number. Its claims are ordinary numeric claims
over a language, and the row that fails here is the one that assumes a
non-empty string has content.

```python
def word_count(text: str) -> int:
    """How many whitespace-separated words `text` holds."""
    return len(text.split())
```

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `word_count` | `for text in L[unicode], f(text) >= 0` | holds | A length is never negative. |
| `word_count` | `for text in L[unicode] \ {""}, f(text) >= 1` | falsified | A whitespace-only string is non-empty and has no words. |
| `word_count` | `for text in L[unicode], is_arbitrary_input_safe(text)` | holds | `str.split` copes with every hazard in the corpus. |

## What is not here yet

Loaders and joiners take rows and frames, and their claims (schema
preservation, key uniqueness, null policy, row-count bounds) wait for the
schema model, where `L[Order]` names a row language read off a
dataclass, a pydantic model or a JSON Schema. The `in` relation, which
spells closure into a different language (`f(text) in L[slug]`) and the
absence of a token (`"<" not in f(text)`), is a change to mathema's
grammar and lands there.
