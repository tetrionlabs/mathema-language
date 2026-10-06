# Narrow a language to what a function accepts

<!-- shop: uploads -->
<!-- requires: django -->

Some functions refuse part of their input on purpose. Django's
`get_valid_filename` raises `SuspiciousFileOperation` for a name it
can't turn into a filename, and a parser raises `ValueError` for text
that isn't in its format. That is good behaviour: the function is saying
where its domain ends. A claim over a language that still holds those
inputs is falsified, because the language is wider than the function's
domain, and the fix is a more specific language. This page shows how to
find out what a function refuses and how to get that language.

## The claim that is too wide

The shop stores each upload under Django's cleaned-up name:

```python
def upload_name(filename: str) -> str:
    """The name an uploaded file is stored under."""
    return get_valid_filename(filename)
```

A stored name must never contain a slash, whatever the user uploads:

```text
for filename in L[unicode], '/' not in upload_name(filename)
    falsified   filename = '': raised SuspiciousFileOperation…
```

The empty name is refused, and so is every name with nothing Django can
keep. The claim is about names Django accepts, and `L[unicode]` holds
names it doesn't.

## See what is refused

`refused_inputs` calls the function on the language's hazards and on
random members, and lists the ones it refuses. Name the errors that mean
a refusal; any other exception is a crash and is raised, not listed:

```python
from django.core.exceptions import SuspiciousFileOperation

from mathema_language.narrowing import refused_inputs
from mathema_language.text import UNICODE

refused = refused_inputs(upload_name, UNICODE, errors=(SuspiciousFileOperation,))
print(len(refused), "refused")
for r in refused[:6]:
    print(f"{r.value!r:10} {r.error}")
```

<!-- output -->
```text
48 refused
''         SuspiciousFileOperation
' '        SuspiciousFileOperation
'\t'       SuspiciousFileOperation
'\n'       SuspiciousFileOperation
'\r\n'     SuspiciousFileOperation
'🙂'        SuspiciousFileOperation
```

Blank names, whitespace, and names made only of characters Django
drops, such as an emoji: each one leaves nothing to store.

## Narrow the language

`narrow_language` returns the language without the refused inputs.
Assign it in a module, beside the function:

```python
UPLOAD_NAMES = narrow_language(UNICODE, upload_name, errors=(SuspiciousFileOperation,))
```

and name it in the claim by its dotted path:

```text
for filename in L[shop.uploads.UPLOAD_NAMES], '/' not in upload_name(filename)
    holds
```

```text
L[unicode]                       every string
L[shop.uploads.UPLOAD_NAMES]     the strings upload_name accepts
                                 (48 of the hazards alone are left out:
                                 '', ' ', '\t', '🙂', ...)
```

The narrowed language keeps everything else a language does: its
members are drawn from the base, its hazards are the base's accepted
ones, and a refinement narrows it further, so the 255-character limit
most filesystems put on a name is one more bound:

```text
for filename in L[shop.uploads.UPLOAD_NAMES, len <= 255], len(upload_name(filename)) <= 255
    holds
```

## State the refusal too

Narrowing says which inputs the claim is about. That the function
refuses the rest is its own claim, and worth keeping, since it is the
behaviour that keeps a bad name out of storage:

```text
f = upload_name
for filename in L[shop.uploads.UPLOAD_NAMES], excluded_outside_domain(filename)
    holds
```

`excluded_outside_domain` tries inputs just outside the narrowed
language, the refused ones among them, and holds when the function
refuses every one.

## When a function refuses almost everything

If the function accepts too few members for random draws to find, the
narrowed language says so: a claim over it is skipped with the reason
"no accepted member". Write the rule as a language of its own then, a
[predicate language](writing-a-language.md) whose members are built to
be accepted, rather than filtered from a wider one.
