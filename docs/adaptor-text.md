# Text annotations

<!-- module: text_models -->

The text adaptor answers two annotations, `str` and `Annotated[str,
...]`, both with the language of every string, `L[unicode]`, and
nothing else. It is how a `str` parameter with no binding gets a
language: the claim needs no `for s in ...`, and the record's note says
the language was inferred and from where. A length marker on the
annotation (`MaxLen(80)`, pydantic's `max_length`) is read by mathema
and refines the language to `L[unicode, len <= 80]`. It needs nothing
installed beyond mathema and this package.

## What it reads

| Annotation | Language | Notes |
|---|---|---|
| `str` | `L[unicode]` | |
| `Annotated[str, MaxLen(80)]` | `L[unicode, len <= 80]` | the markers are read by attribute, `max_length` and `min_length` |
| `str \| None`, `Optional[str]` | not answered | how a missing value is admitted is decided in mathema itself |
| anything else | not answered | |

## A worked claim

```python
from typing import Annotated

from annotated_types import MaxLen


def shout(s: str) -> str:
    """Upper case."""
    return s.upper()


def label(s: Annotated[str, MaxLen(8)]) -> str:
    """The label, cut to the eight characters it is declared to fit."""
    return s[:8]
```

| Function | Claim | Verdict | Why |
|---|---|---|---|
| `shout` | `len(f(s)) == len(s)` | falsified | Inferred `L[unicode]`, and `'ΐ'` upper-cases to three code points. |
| `label` | `f(s) == s` | holds | Inferred `L[unicode, len <= 8]`, inside which the cut changes nothing. |

## A non-member

A text language explains a non-member by the first character it
refuses, at its index.

```python
from mathema_language.text import ASCII

for problem in ASCII.explain("café"):
    print(repr(problem.path), "|", problem.predicate)
```

<!-- output -->
```text
'[3]' | ascii alphabet
```
