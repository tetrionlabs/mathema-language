<!-- github-only -->
> This page is part of the mathema documentation, [read it on the site](https://mathema.tetrionlabs.com/language/reference/how-to-narrow-a-language/).
<!-- /github-only -->

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

This runs anywhere you can import the function, a Python shell or a
scratch script, since it is a question you ask once rather than code
the shop keeps:

```python
from django.core.exceptions import SuspiciousFileOperation

from mathema_language.narrowing import refused_inputs
from mathema_language.text import UNICODE
from shop.uploads import upload_name

refused = {r.value for r in refused_inputs(upload_name, UNICODE,
                                           errors=(SuspiciousFileOperation,))}
for name in ["", " ", "\t", "🙂", "report.pdf"]:
    print(f"{name!r:14} refused: {name in refused}")
```

<!-- output -->
```text
''             refused: True
' '            refused: True
'\t'           refused: True
'🙂'            refused: True
'report.pdf'   refused: False
```

Blank names, whitespace, and names made only of characters Django
drops, such as an emoji, each leave nothing to store. The full list
runs to a few dozen of the language's hazards, and how many depends on
the Unicode version your Python ships.

## Narrow the language

`narrow_language` returns the language without the refused inputs.
The narrowed language is an ordinary Python object, so it lives in your
code, in the same module as the function it is narrowed by. In the shop
that is `shop/uploads.py`, the whole of which is:

```python
from django.core.exceptions import SuspiciousFileOperation
from django.utils.text import get_valid_filename

from mathema_language.narrowing import narrow_language
from mathema_language.text import UNICODE


def upload_name(filename: str) -> str:
    """The name an uploaded file is stored under."""
    return get_valid_filename(filename)


UPLOAD_NAMES = narrow_language(UNICODE, upload_name, errors=(SuspiciousFileOperation,))
```

The claim is a separate thing. It names the language by its dotted
path, `shop.uploads.UPLOAD_NAMES`, the module path and the variable, and
can live wherever claims live: in `upload_name`'s docstring under
`Claims:`, in a claims file, or on the command line with
`mathema check shop/uploads.py:upload_name --claim "..."`:

```text
for filename in L[shop.uploads.UPLOAD_NAMES], '/' not in upload_name(filename)
    holds
```

```text
L[unicode]                       every string
L[shop.uploads.UPLOAD_NAMES]     the strings upload_name accepts
                                 (blank names, whitespace and '🙂'
                                 among the hazards left out)
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
