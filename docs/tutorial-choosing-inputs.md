# Choosing the inputs

<!-- shop: text -->

A claim has two halves: the rule, and the inputs it covers. The rule is
usually the easy part to write. This page is about the other half, the
`for ... in` that says which inputs the function has to get right,
because that choice decides what a verdict means.

## The text languages

A string's domain is a language, written `L[...]`. These cover most
code:

| Language | Every string of |
|---|---|
| `L[unicode]` | any code points at all, lone surrogates and controls included |
| `L[printable]` | characters that print (`str.isprintable`) |
| `L[latin-1]` | code points up to 0xff |
| `L[ascii]` | code points up to 0x7f |
| `L[alpha]`, `L[alnum]`, `L[digit]` | ASCII letters, letters and digits, digits |
| `L[unicode_alpha]`, `L[unicode_alnum]` | letters, or letters and digits, in any script |
| `L[identifier]` | a Python identifier |

[Languages](languages.md) lists the rest, formats such as `L[uuid]` and
`L[email]` among them, and [Formats](formats.md) uses them.

## Narrowing by length

The shop's header shows the username upper-cased, in a box 32 characters
wide, and usernames are at most 32 characters:

```python
def display_name(username: str) -> str:
    """The username as shown in the header, upper-cased."""
    return username.upper()
```

`len <= 32` inside the brackets narrows a language to its strings of at
most 32 code points, so the claim that the header fits is:

```text
for username in L[unicode, len <= 32], len(display_name(username)) <= 32
    falsified   username='aﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁﬁ': 33 vs 32
```

```text
username  'aﬁﬁﬁ…ﬁ'      17 code points: 'a', then 16 of U+FB01 LATIN SMALL LIGATURE FI
header    'AFIFIFI…FI'  33 code points, since each ﬁ upper-cases to two
```

Upper-casing can make a string longer. It is tempting to decide that
usernames are European and move on, but `L[latin-1]` fails the same way,
on the German sharp s:

```text
for username in L[latin-1, len <= 32], len(display_name(username)) <= 32
    falsified   username='aßßßßßßßßßßßßßßßß': 33 vs 32
```

Only ASCII keeps its length when upper-cased:

```text
for username in L[ascii, len <= 32], len(display_name(username)) <= 32
    holds
```

So there are two honest fixes, and the claim makes you pick one. Either
usernames really are ASCII, in which case the signup form should refuse
anything else and the claim over `L[ascii, len <= 32]` is the right one,
or they aren't, and `display_name` has to cut its result to 32 after
upper-casing, not before. What won't do is a claim over `L[ascii]` for a
form that takes any text: the claim would hold, and say nothing about
the names the shop actually gets.

## Leaving values out

The avatar shows the first letter of a user's name:

```python
def first_initial(name: str) -> str:
    """The avatar letter shown for a user."""
    return name[0].upper()
```

```text
for name in L[unicode], len(first_initial(name)) == 1
    falsified   name='': raised IndexError…
```

A name with nothing in it has no first letter. If the shop never stores
an empty name, say so by leaving it out with `\`, the set difference:

```text
for name in L[unicode] \ {''}, len(first_initial(name)) == 1
    falsified   name='ΐ': 3 vs 1
```

`L[unicode, len >= 1]` says the same thing as `L[unicode] \ {''}`; the
exclusion is for any particular value, such as the `'NA'` a spreadsheet
writes for a missing name.

The second failure is different. `ΐ` (Greek iota with dialytika and
tonos) upper-cases to three code points, `Ϊ́`, which a screen still shows
as one letter. The code is fine; it is the claim that asked for the
wrong thing, one code point, when what the avatar needs is at least one:

```text
for name in L[unicode] \ {''}, len(first_initial(name)) >= 1
    holds
```

Most falsified claims end one of these two ways, a change to the code or
a change to the claim, and both are progress: either way the rule is
now written down and checked.

## Choosing well

Start from what the function is actually given, not from what makes the
claim pass. If the input comes from a form, a file or another service,
that is usually `L[unicode]`, and every narrowing (a shorter length, a
smaller alphabet, a value left out) should be one the code that calls
the function really enforces.

Next: [Formats](tutorial-formats.md).
