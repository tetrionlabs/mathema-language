<!-- github-only -->
> This page is part of the mathema documentation, [read it on the site](https://mathema.tetrionlabs.com/language/reference/formats/).
<!-- /github-only -->

# Formats and identifiers

<!-- shop: formats text -->

Much of the text an application handles has a format: an order number,
a UUID, a date, an IP address, a token, a colour, an attribute name, a
file name passed to a shell. Each format is a language here, decided by
the standard library's own parser, never a regular expression standing
in for it, so a claim over `L[uuid]` covers every spelling `uuid.UUID`
reads, not only the one a developer had in mind. The claims that matter
for a format are the same few everywhere: a parser rejects what is not
in its language, a normaliser is idempotent, a renderer's output is in
the language, and a round trip gives back what went in, or does not,
and the witness says which spelling breaks it.

The examples are the shop's own, from `examples/shop/formats.py`.

## The format languages

| Language | Members | Decided by |
|---|---|---|
| `L[digit]` | strings of the ten ASCII digits | `c in "0123456789"` |
| `L[alpha]`, `L[alnum]` | letters, and letters with digits, in any script | `str.isalpha`, `str.isalnum` |
| `L[identifier]` | Python identifiers | `str.isidentifier` |
| `L[uuid]` | every spelling `uuid.UUID` reads: hyphenated, bare, braced, `urn:uuid:` | `uuid.UUID` |
| `L[iso_date]`, `L[iso_datetime]` | ISO 8601 dates and times as this Python reads them | `date.fromisoformat`, `datetime.fromisoformat` |
| `L[ipv4]`, `L[ipv6]` | addresses | `ipaddress.IPv4Address`, `ipaddress.IPv6Address` |
| `L[base64]` | canonical base64 | `b64decode(validate=True)`, re-encoded equal |
| `L[hex]` | what `bytes.fromhex` reads, spaces included | `bytes.fromhex` |
| `L[slug]` | lower-case words joined by single hyphens | `[a-z0-9]+(-[a-z0-9]+)*` |
| `L[shell_safe]` | a word the shell reads literally | `shlex.quote(s) == s` |

## Parse, and reject the rest

A parser's first job is to refuse what is not in its language, and
`excluded_outside_domain` checks exactly that: it feeds the function the
language's near non-members and falsifies if one is accepted without an
error.

```python
def parse_order_id(text: str) -> uuid.UUID:
    """The order id in a URL, or a ValueError when it is not one."""
    return uuid.UUID(text)
```

```text
f = parse_order_id
for text in L[uuid], excluded_outside_domain(text)
    holds
```

## Normalise, and normalise once

A normaliser stores one spelling for many, so it has to be idempotent,
and whether it keeps the spelling it was given is a separate claim that
is usually false:

```python
def normalise_order_id(text: str) -> str:
    """The order id as the database stores it."""
    return str(uuid.UUID(text))


def normalise_date(text: str) -> str:
    """A delivery date as the shop stores it."""
    return dt.date.fromisoformat(text).isoformat()


def normalise_timestamp(text: str) -> str:
    """An event time as the shop stores it."""
    return dt.datetime.fromisoformat(text).isoformat()


def normalise_colour(text: str) -> str:
    """A colour's hex bytes as the theme file stores them."""
    return bytes.fromhex(text).hex()
```

```text
f = normalise_order_id
for text in L[uuid], f(f(text)) == f(text)
    holds

for text in L[uuid], f(text) == text
    falsified   text = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa': 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa' vs 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'

f = normalise_date
for text in L[iso_date], f(f(text)) == f(text)
    holds

f = normalise_timestamp
for text in L[iso_datetime], f(f(text)) == f(text)
    holds

f = normalise_colour
for text in L[hex], f(f(text)) == f(text)
    holds

for text in L[hex], f(text) == text
    falsified   text = 'aA': 'aa' vs 'aA'
```

A bare 32-digit UUID is a UUID, and it comes back hyphenated, so a
lookup that compares the stored id with the one in the URL misses it.

## Render into a language

A function that produces a format holds its output to that language
with `in`:

```python
def render_quantity(n: int) -> str:
    """A quantity as it is printed on the invoice."""
    return str(n)


def anonymise_ip(address: str) -> str:
    """A visitor's address with the last part zeroed, for analytics."""
    return ".".join(address.split(".")[:3] + ["0"])


def attribute_name(label: str) -> str:
    """A form label turned into the attribute name the template uses."""
    return label.strip().replace(" ", "_").lower()
```

```text
f = render_quantity
for n in N, f(n) in L[digit]
    holds

f = anonymise_ip
for address in L[ipv4], f(address) in L[ipv4]
    holds

for address in L[ipv6], f(address) in L[ipv6]
    falsified   address = '::': '::.0' is not in L[ipv6]

f = attribute_name
for label in L[identifier], f(label) in L[identifier]
    holds

for label in L[alnum], f(label) in L[identifier]
    falsified   label = '': '' is not in L[identifier]
```

The anonymiser was written for IPv4 and quietly produces garbage for
the IPv6 addresses the same log holds.

## Round trips

A decoder followed by an encoder gives back what went in, over the
language where that is meant to be true:

```python
def reencode_token(token: str) -> str:
    """An API token as the gateway passes it on."""
    return base64.b64encode(base64.b64decode(token)).decode("ascii")
```

```text
f = reencode_token
for token in L[base64], f(token) == token
    holds
```

## Shell commands

`L[shell_safe]` is the language of words a shell reads literally, and a
command built from a file name is only safe over it, or when the name
is quoted:

```python
def delete_command(filename: str) -> list:
    """The command that deletes an uploaded file, split into arguments
    the way the shell will."""
    return shlex.split(f"rm {filename}")


def delete_command_quoted(filename: str) -> list:
    """The same command with the filename quoted."""
    return shlex.split(f"rm {shlex.quote(filename)}")
```

```text
f = delete_command
for filename in L[printable], f(filename) == ["rm", filename]
    falsified   filename = '': ['rm'] vs ['rm', '']

for filename in L[shell_safe], f(filename) == ["rm", filename]
    holds

f = delete_command_quoted
for filename in L[printable], f(filename) == ["rm", filename]
    holds
```

An empty name drops an argument, and a name with a space in it splits
into two, which is how a delete of one uploaded file becomes a delete of
two.

## Recipes

| To say | Write |
|---|---|
| the parser rejects what is not in the format | `for s in L[uuid], excluded_outside_domain(s)` |
| normalising twice is normalising once | `for s in L[iso_date], f(f(s)) == f(s)` |
| the output is in the format | `for n in N, f(n) in L[digit]` |
| decode then encode gives it back | `for s in L[base64], f(s) == s` |
| the function only works for part of a format | the same claim over the narrower language, beside the falsified one |
