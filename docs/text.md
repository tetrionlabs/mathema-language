# Text

<!-- shop: text -->

A function that takes a string is claimed over a language, the set of
strings it is meant to handle, written where a numeric claim writes a
range: `for name in L[unicode], ...`. `L[unicode]` is every string
Python can hold, lone surrogates included, and it is the language to
reach for when a function takes text from a user, a file or a request,
since that is what can arrive. A narrower language says what the caller
guarantees. Every language here is decided by Python's own reading of
it, and each one tries its hazards, the strings real code gets wrong,
before any random member.

The examples on this page are the shop's text helpers, from
`examples/shop/text.py`.

## The text languages

| Language | Members | Use it for |
|---|---|---|
| `L[unicode]` | every `str` | anything a user, file or request can send |
| `L[ascii]` | strings over the 128 ASCII code points | protocols and formats that are ASCII by definition |
| `L[latin-1]` | strings the latin-1 codec encodes | legacy encodings, HTTP header values |
| `L[printable]` | what `str.isprintable` accepts | text meant to be shown or logged |
| `L[control]` | the control characters and the space | where a newline or NUL is the danger |
| `L[invisible]` | zero-width, byte-order and bidirectional marks | text that looks empty or reorders itself |
| `L[combining]` | combining marks | accents stacked on a letter |
| `L[surrogate]` | lone surrogates | code points no encoding can write |
| `L[compatibility]` | characters NFKC normalises to something else | ligatures, fullwidth forms, `℀` |
| `L[astral]` | characters past the basic multilingual plane | emoji and rarer scripts |

Every one of them includes the empty string, the way a character class
repeated any number of times does; `L[unicode] \ {""}` leaves it out.

## Length

A column, a field or a protocol limit bounds length, and a refinement
inside the brackets says so: `L[unicode, len <= 32]` is every string of
at most 32 code points, counted the way `len` counts. The probe tries
the members at the bound, and, for a length claim, each character whose
length changes under case mapping or normalisation repeated up to the
bound, which is how a name that fits the column stops fitting it once
it is upper-cased:

```python
def display_name(username: str) -> str:
    """The username as shown in the header, upper-cased."""
    return username.upper()
```

```text
f = display_name
for username in L[unicode, len <= 32], len(f(username)) <= 32
    falsified   username = 'aﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁ': 33 vs 32
```

`ﬁ` is one code point and upper-cases to the two letters `FI`. A
parameter annotated with a maximum length infers the refined language
on its own, with no binding written:

```python
def short_title(title: Annotated[str, MaxLen(60)]) -> str:
    """The title, cut to the sixty characters the column holds."""
    return title[:60]
```

```text
f = short_title
for title in L[unicode], len(f(title)) <= 60
    holds
```

## Case and normal forms

Two strings a reader sees as the same can be different code points,
and a function that stores or compares names has to decide whether they
are the same. The text vocabulary (`nfc`, `nfd`, `nfkc`, `nfkd`,
`casefold`, `lower`, `upper` and more, in
`mathema_language.text`) is bound with `let` and used inside
the claim:

```python
def username_key(name: str) -> str:
    """The key an account is stored under, so two spellings of a name
    find the same account."""
    return name.strip().lower()
```

```text
f = username_key
let nfkc = mathema_language.text.nfkc, for name in L[unicode], f(nfkc(name)) == f(name)
    falsified   name = '℀': 'a/c' vs '℀'
```

`℀` normalises to the three characters `a/c`, and `username_key` never
normalises, so the two register as different accounts. `L[invisible]` is
the language of characters that are there but show nothing, which is
where a check for an empty name goes wrong:

```python
def is_blank(name: str) -> bool:
    """Whether a display name has nothing visible in it."""
    return not name.strip()
```

```text
f = is_blank
for name in L[invisible] \ {""}, f(name) == True
    falsified   name = '\u200b': False vs True
```

A name made of a zero-width space is not blank to `strip`, and shows
nothing on the page.

## Encodings

A string meets an encoding when it is written to a header, a file or a
database, and the claim family `is_encoding_safe` feeds a function the
characters at an alphabet's edges and reports an unguarded
`UnicodeError`:

```python
def header_value(value: str) -> str:
    """The value as it goes on the wire in an HTTP header."""
    return value.encode("ascii").decode("ascii")


def to_bytes(text: str) -> bytes:
    """The text as the database driver sends it."""
    return text.encode("utf-8")
```

```text
f = header_value
for value in L[latin-1], f(value) == value
    falsified   value = '\xa0': raised UnicodeEncodeError

for value in L[ascii], f(value) == value
    holds

f = to_bytes
for text in L[unicode], is_encoding_safe(text)
    falsified   text = '\ud800' (unnamed, category Cs) (inside L[unicode]) raised UnicodeEncodeError

for text in L[printable], is_encoding_safe(text)
    holds
```

The no-break space is latin-1 and not ASCII. A lone surrogate is a
`str` Python can hold and UTF-8 cannot write, which is a real input
wherever text arrives through JSON's `\ud800` escapes. Lengths differ
between runtimes too: a character past the basic multilingual plane is
one code point to Python and two to JavaScript:

```python
def js_length(text: str) -> int:
    """The length the browser's JavaScript reports for the text."""
    return len(text.encode("utf-16-le")) // 2
```

```text
f = js_length
for text in L[printable], f(text) == len(text)
    falsified   text = '😀': 2 vs 1

for text in L[astral] \ {""}, f(text) == 2 * len(text)
    holds
```

## Crashes on arbitrary input

`is_language_defined` feeds a function the language's hazards and
its near non-members and reports a crash the function did not guard
(an `IndexError`, a `KeyError`, a `TypeError`), shrunk to the smallest
string that still crashes. A deliberate `ValueError` is a rejection, not
a crash; a value claim is stricter, since any raise inside its domain
falsifies it:

```python
def first_initial(name: str) -> str:
    """The avatar letter shown for a user."""
    return name[0].upper()


def parse_quantity(text: str) -> int:
    """The quantity typed into a form, 0 when it is not a number."""
    return int(text) if text.isdigit() else 0
```

```text
f = first_initial
for name in L[unicode], is_language_defined(name)
    falsified   name = '' (inside L[unicode]) raised IndexError

f = parse_quantity
for text in L[unicode], f(text) >= 0
    falsified   text = '²': raised ValueError

for text in L[digit], f(text) >= 0
    holds
```

`'²'.isdigit()` is true and `int('²')` refuses it, so the guard lets
through the one kind of digit the parse cannot read.

## What an output may contain

`in` and `not in` hold an output to a language or keep a token out of
it, which is how an escaper, a sanitiser or a header builder is
claimed:

```python
def render_comment(body: str) -> str:
    """A comment body, safe to put in a page."""
    return html.escape(body)


def log_line(message: str) -> str:
    """A message made safe to write to a log file."""
    return "".join(c for c in message if c.isprintable())


def note_header(note: str) -> str:
    """An HTTP header carrying a free-text note."""
    return "X-Note: " + note
```

```text
f = render_comment
for body in L[unicode], "<" not in f(body)
    holds

f = log_line
for message in L[unicode], f(message) in L[printable]
    holds

f = note_header
for note in L[unicode], "\n" not in f(note)
    falsified   note = '\n': '\n' is in f(note)

for note in L[printable], "\n" not in f(note)
    holds
```

A note with a newline in it ends the header and starts another, which
is header injection; over `L[printable]` it cannot happen, and that is
the language the caller has to guarantee, or the function has to
enforce.

## Recipes

| To say | Write |
|---|---|
| it never crashes on user text | `for s in L[unicode], is_language_defined(s)` |
| it writes any text without an encoding error | `for s in L[unicode], is_encoding_safe(s)` |
| its output fits the column the input fits | `for s in L[unicode, len <= 32], len(f(s)) <= 32` |
| it gives the same answer for every spelling | `let nfkc = mathema_language.text.nfkc, for s in L[unicode], f(nfkc(s)) == f(s)` |
| it never emits a character | `for s in L[unicode], "<" not in f(s)` |
| its output stays in a language | `for s in L[unicode], f(s) in L[printable]` |
| applying it twice changes nothing | `for s in L[unicode], f(f(s)) == f(s)` |
