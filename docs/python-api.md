# Using a language from Python

<!-- shop: forms -->

Claims are the way to use a language. For tools, tests and adaptors
that need one directly, a language is an ordinary object: `adapt_row`
gives the language of a schema, and every language answers the same
questions.

| Method | Answers |
|---|---|
| `contains(value)` | whether the value is a member |
| `explain(value)` | why not: problems, each a path into the value and what failed there, or `None` for a member |
| `sample(rng)` | a random member |
| `hazards()` | the members every probe tries first, each with a kind and a note |
| `outside(rng)` | a near non-member, or `None` when the language has no outside |
| `shrink(value)` | smaller members, one at a time, largest steps first |
| `fields()` | a record language's field bounds, as the derive route reads them |

The explanation is the one a witness quotes:

```python
from mathema_language.schema.adaptors import adapt_row

language = adapt_row(SignupForm)
bad = SignupForm.model_construct(username="ab", age=12)
for problem in language.explain(bad):
    print(repr(problem.path), "|", problem.predicate)
```

<!-- output -->
```text
'.username' | String should have at least 3 characters
'.age' | Input should be greater than or equal to 13
```

`mathema.languages.resolve_language("json")` gives a named language the
same way a claim resolves it.
