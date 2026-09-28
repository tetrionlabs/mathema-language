# Claim families

<!-- shop: text formats forms -->

A claim family is a named claim that feeds a function the inputs of one
hazard class and reports what goes wrong, with a witness shrunk to the
smallest input that still shows it. Over a language, each family draws
from the language's own hazards and near non-members, and a witness
says whether it lies inside or outside the claim's domain.

| Family | Feeds the function | Falsified when |
|---|---|---|
| `is_arbitrary_input_safe(s)` | the language's hazards, members and near non-members | it raises an error it did not guard, an `IndexError`, `KeyError`, `TypeError`, `AttributeError`, `UnicodeError`, `RecursionError` or `OverflowError` |
| `excluded_outside_domain(s)` | values just outside the language | it accepts one without an error |
| `is_encoding_safe(s)` | characters at the language's alphabet edges, and the codecs the body names | it raises an unguarded `UnicodeError` |
| `is_length_safe(s)` | the language's longest members and overlong inputs | it crashes, or runs past mathema's time limit |

A deliberate `ValueError` is a rejection, not a crash, so
`is_arbitrary_input_safe` holds for a parser that raises one; a value
claim over the same domain is stricter, since any raise inside its
domain falsifies it.

```text
f = first_initial
for name in L[unicode], is_arbitrary_input_safe(name)
    falsified   name = '' (inside L[unicode]) raised IndexError

f = to_bytes
for text in L[unicode], is_encoding_safe(text)
    falsified   text = '\ud800' (unnamed, category Cs) (inside L[unicode]) raised UnicodeEncodeError

f = parse_order_id
for text in L[uuid], excluded_outside_domain(text)
    holds

f = welcome_message
for form in L[shop.forms.SignupForm], excluded_outside_domain(form)
    falsified   form = SignupForm(username='aaa', age=12) (outside L[shop.forms.SignupForm] at .age: Input should be greater than or equal to 13)
```

`excluded_outside_domain`'s witness says why the value is outside, in
the language's own words, a path into the record and what failed there.
