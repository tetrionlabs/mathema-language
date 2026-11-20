# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The words this package gives `L[...]`, registered with mathema's
word registry under the `mathema.language_refinements` entry points.

Pattern words, over any text language:

- `matches (P)`: the whole text is in the pattern;
- `contains (P)`: some part of the text is;
- `starts with (P)`, `ends with (P)`: its beginning, its end.

`P`, the one argument, is a quoted string, read as that literal text; a
call `re(r"...", python, ignore case)`, a Python regular expression with
its dialect and flags; a call `shape("AA99", A = upper)`, a shape; or a
dotted name, resolved when the language is, of a compiled pattern or a
`Shape`. Each reads as one Python regular expression under the
predicate, and the refined language is the base met with
`pattern_language` of it: membership is the base's and `re`'s, and the
term, where the base states one, is the intersection of the two terms
(with a complement under `not`).

`re(...)` is written canonically with the pattern first, as a raw string
where it can be one, then the dialect, always, then the flags sorted:
`re(r"[a-z]+")` is `re(r"[a-z]+", python)`. Flags are the words `ascii
only`, `dot all`, `ignore case`, `multi line`, `verbose`, in any casing
and spacing; inline flags at the very start of the pattern (`(?i)`) are
read as their words. Only `python` (or `py`) is a dialect for now:
`javascript` is refused as not available yet, and the other dialect
words are reserved.

Operators read as words: `^= "a"` is `starts with ("a")`, `$=` `ends
with`, `*=` `contains`; `== "a"` is `matches ("a")`, a literal only;
`in P` is `matches (P)`, a pattern or an object only.

`within (...)` bounds a path, an IP address or a date
(`mathema_language.text.within`), and is also read in its keyword
spelling, `within "/root"`. `shape (...)` pictures text over `ascii` or
`unicode` (`mathema_language.text.shape`).

`ALPHABET` builds the language an alphabet expression heads,
`L[lower + digit + "_"]`, every string over the alphabet
(`mathema_language.text.alphabet`).

A word read where it has no meaning is refused by mathema with the
word's `kinds`, an example, and the language its `suggest` function
guesses was meant. `reads_call` says which calls in code a word states:
a compiled pattern's `fullmatch` is `matches`, its `search` `contains`,
its `match` `starts with`.
"""
from __future__ import annotations

import ast
import difflib
import functools
import importlib
import random
import re
from dataclasses import dataclass
from typing import Any

from ._surface import AlphabetConstructor, PredicateWord
from .text import _algebra, _regular
from .text._kit import TextLanguage
from .text.alphabet import NAMES, Alphabet, alphabet_language, parse_alphabet
from .text.shape import SHAPE, Shape, shape_examples, shape_language, suggest_shape
from .text.within import WITHIN, suggest_within, within_examples, within_refusal

#: the pattern words and the `re` call each one is of a compiled pattern
PATTERN_WORDS = {"matches": "fullmatch", "contains": "search", "starts with": "match",
                 "ends with": None}

#: the flag words `re(...)` takes, each with its `re` flag
FLAGS = {word: flag for flag, word in _regular.FLAG_WORDS.items()}

#: the dialect words: the one that is read, the one refused as not yet available, and the
#: reserved ones, each spelling mapped to its canonical word
DIALECTS = {"python": "python", "py": "python"}
UNAVAILABLE = {"javascript": "javascript", "js": "javascript", "ecma": "javascript"}
RESERVED = {"rust": "rust", "cpp": "cpp", "c++": "cpp", "go": "go", "re2": "go", "java": "java",
            "dotnet": "dotnet", "csharp": "dotnet", ".net": "dotnet", "ruby": "ruby", "pcre": "pcre",
            "perl": "pcre", "php": "pcre", "posix": "posix", "ere": "posix",
            "posix basic": "posix basic", "bre": "posix basic"}

_INLINE = {"a": "ascii only", "i": "ignore case", "m": "multi line", "s": "dot all", "x": "verbose"}
_CALL = re.compile(r"^(?P<name>[A-Za-z_][A-Za-z_ ]*?)\s*\((?P<inside>.*)\)$", re.DOTALL)
_DOTTED = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+$")
_STRING = re.compile(r"""^[rR]?(?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')$""", re.DOTALL)


def _key(word: str) -> str:
    """Intent:
        A word as it is matched: lower case, with no spaces or underscores.
    """
    return re.sub(r"[\s_]+", "", word).lower()


def _split(text: str) -> list[str]:
    """Intent:
        The parts of `text` between its top-level commas, each stripped: a comma inside
        quotes or brackets separates nothing.
    """
    parts: list[str] = []
    depth, quote, start, at = 0, "", 0, 0
    while at < len(text):
        ch = text[at]
        if quote:
            if ch == "\\":
                at += 1
            elif ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(text[start:at].strip())
            start = at + 1
        at += 1
    parts.append(text[start:].strip())
    return parts


def _string(text: str) -> str | None:
    """Intent:
        The string a quoted argument states, read as a Python string literal (raw with an `r`
        in front), or None when `text` is not one quoted string.
    """
    if _STRING.match(text.strip()) is None:
        return None
    try:
        value = ast.literal_eval(text.strip())
    except (ValueError, SyntaxError):
        return None
    return value if isinstance(value, str) else None


def _quoted(text: str) -> str:
    """Intent:
        `text` between double quotes as a claim writes a literal: a backslash before each
        backslash and double quote, and control characters as their escapes.
    """
    out = text.replace("\\", "\\\\").replace('"', '\\"')
    return '"' + "".join(c if c.isprintable() else c.encode("unicode_escape").decode("ascii") for c in out) + '"'


def _raw(pattern: str) -> str:
    """Intent:
        A pattern's text as a claim writes it: a raw string in double quotes where one can
        hold it (no double quote, no control character, no backslash at the end), else an
        ordinary quoted string.
    """
    if '"' in pattern or pattern.endswith("\\") or not all(c.isprintable() for c in pattern):
        return _quoted(pattern)
    return 'r"' + pattern + '"'


def version_pin(word: str) -> str:
    """Intent:
        The Python version a pin after the dialect names: `python 3.13` (or `py 3.13`) is
        `3.13`.

    Raises:
        ValueError: the pin is not `python` and a major and minor number, or the version is
            not one the package covers.
    """
    found = re.fullmatch(r"(?:python|py) ?([0-9]+\.[0-9]+)", word)
    if found is None:
        raise ValueError(f"a version is written python 3.13, not {word!r}")
    versions = _regular.versions_data()["versions"]
    if found.group(1) not in versions:
        raise ValueError(f"python {found.group(1)} is not a supported version; the versions are "
                         f"{', '.join(versions)}")
    return found.group(1)


def re_text(pattern: str, flags: int = 0, version: str | None = None) -> str:
    """Intent:
        The canonical text of a Python pattern as an argument: `re(r"...", python)`, with the
        version after the dialect when one is pinned (`python 3.13`), then the words of
        `flags`, sorted.

    Raises:
        ValueError: `flags` holds a flag with no word (LOCALE, DEBUG).
    """
    known = 0
    for flag in FLAGS.values():
        known |= int(flag)
    if int(flags) & ~known & ~int(re.UNICODE):
        raise ValueError(f"a flag of {flags!r} has no word; the flags are {', '.join(sorted(FLAGS))}")
    words = sorted(word for word, flag in FLAGS.items() if int(flags) & int(flag))
    dialect = "python" if version is None else f"python {version}"
    return "re(" + ", ".join([_raw(pattern), dialect, *words]) + ")"


def read_re(text: str) -> tuple[str, int] | None:
    """Intent:
        The pattern and flags an argument written `re(...)` states, or None when `text` is not
        a call of `re`. Inline flags at the very start of the pattern are taken out of it and
        read as flags.

    Raises:
        ValueError: the first argument is not a quoted pattern; a word is a dialect that is
            not available or is reserved, a version that does not read, or neither a dialect
            nor a flag (the nearest word is offered); two dialects are named; or the pattern
            does not compile.
    """
    found = _read_re(text)
    return None if found is None else found[:2]


def _re_version(text: str) -> str | None:
    """Intent:
        The Python version an argument written `re(...)` pins after its dialect, or None when
        it pins none or `text` is not a call of `re`.

    Raises:
        ValueError: as `read_re`.
    """
    found = _read_re(text)
    return None if found is None else found[2]


def _read_re(text: str) -> tuple[str, int, str | None] | None:
    """Intent:
        The pattern, flags and pinned version of an argument written `re(...)`, or None.
    """
    call = _CALL.match(text.strip())
    if call is None or _key(call.group("name")) != "re":
        return None
    version: str | None = None
    parts = _split(call.group("inside"))
    pattern = _string(parts[0]) if parts and parts[0] else None
    if pattern is None:
        raise ValueError('re takes a quoted pattern first: re(r"[a-z]+", python)')
    flags, dialects = 0, []
    lead = re.match(r"\(\?([aimsx]+)\)", pattern)
    if lead is not None:
        pattern = pattern[lead.end():]
        for letter in lead.group(1):
            flags |= int(FLAGS[_INLINE[letter]])
    flag_keys = {_key(word): word for word in FLAGS}
    refused = ""
    for part in parts[1:]:
        word = re.sub(r"\s+", " ", part.strip().lower())
        key = _key(part)
        if key in flag_keys:
            flags |= int(FLAGS[flag_keys[key]])
        elif word in DIALECTS:
            dialects.append(DIALECTS[word])
        elif word in UNAVAILABLE:
            refused = refused or "the javascript dialect is not available yet"
        elif word in RESERVED:
            refused = refused or f"the {RESERVED[word]} dialect is reserved, not available yet"
        elif re.match(r"(?:python|py)?\s*[0-9]", word):
            version = version_pin(word)
            dialects.append("python")
        else:
            near = difflib.get_close_matches(word, [*FLAGS, *DIALECTS], n=1)
            raise ValueError(f"{part!r} is neither a dialect nor a flag of re; the flags are "
                             f"{', '.join(sorted(FLAGS))}"
                             + (f". Did you mean {near[0]}?" if near else ""))
    if refused:
        raise ValueError(f"{refused}. Did you mean {re_text(pattern, flags)}?")
    if len(dialects) > 1:
        raise ValueError("re names one dialect")
    try:
        re.compile(pattern, flags)
    except (re.error, RecursionError, OverflowError) as e:
        raise ValueError(f"the pattern {_raw(pattern)} does not compile: {e}") from e
    return pattern, flags, version


def _bindings(parts: list[str]) -> dict[str, str]:
    """Intent:
        The bindings written after a picture, `W = alnum + "_"`, each symbol with the
        canonical text of its alphabet.

    Raises:
        ValueError: a part is not `SYMBOL = alphabet expression`, or a symbol is bound twice.
    """
    out: dict[str, str] = {}
    for part in parts:
        symbol, equals, expression = part.partition("=")
        symbol = symbol.strip()
        if not equals or len(symbol) != 1 or not symbol.isalnum() or expression.startswith("="):
            raise ValueError(f'a binding is SYMBOL = alphabet, W = alnum + "_", not {part!r}')
        if symbol in out:
            raise ValueError(f"the symbol {symbol} is bound twice")
        out[symbol] = parse_alphabet(expression.strip()).text
    return out


def shape_text(shape: Shape, call: bool = True) -> str:
    """Intent:
        The canonical text of a shape as an argument: `shape("AA99", A = upper)` as a call
        inside another word's brackets, or its arguments alone.
    """
    return f"shape({shape.arguments})" if call else shape.arguments


def read_shape(parts: list[str], base: str = "unicode") -> Shape:
    """Intent:
        The shape a picture and its bindings state over the base: the first part a quoted
        picture, the rest bindings.

    Raises:
        ValueError: the first part is not a quoted picture, a binding does not read, or the
            shape does not read (a `ShapeError` says what was expected and where).
    """
    picture = _string(parts[0]) if parts and parts[0] else None
    if picture is None:
        raise ValueError('shape takes a quoted picture first: shape ("AA99[ ]9AA")')
    return Shape(picture, base, _bindings(parts[1:]))


def _shape_call(text: str) -> list[str] | None:
    """Intent:
        The parts of an argument written `shape(...)`, or None when `text` is not a call of
        `shape`.
    """
    call = _CALL.match(text.strip())
    if call is None or _key(call.group("name")) != "shape":
        return None
    return _split(call.group("inside"))


def canonical_pattern_argument(text: str, sugar: str | None = None) -> str:
    """Intent:
        One argument of a pattern word in canonical text: a literal in double quotes,
        `re(r"...", python, flags)`, `shape("...", bindings)`, or a dotted name as written.

    Raises:
        ValueError: the argument is none of those, does not read, or is not the kind the
            operator `sugar` takes (`==` a literal, `in` a pattern or an object).
    """
    literal = _string(text)
    pattern = None if literal is not None else read_re(text)
    parts = None if literal is not None or pattern is not None else _shape_call(text)
    if sugar == "==" and literal is None:
        raise ValueError(f"a string is not equal to a pattern: == takes a quoted literal; "
                         f"write matches ({text.strip()})")
    if sugar == "in" and literal is not None:
        raise ValueError(f"in takes a pattern or an object; for the literal text write == {_quoted(literal)}")
    if literal is not None:
        return _quoted(literal)
    if pattern is not None:
        return re_text(*pattern, _re_version(text))
    if parts is not None:
        return shape_text(read_shape(parts))
    if _DOTTED.match(text.strip()):
        return text.strip()
    raise ValueError(f'{text.strip()!r} is not a pattern: write a quoted literal, re(r"...", python), '
                     f'shape("...") or the dotted name of a compiled pattern')


def _object(name: str) -> Any:
    """Intent:
        The object a dotted name names: the longest importable module, then attributes.

    Raises:
        ValueError: nothing has that name.
    """
    parts = name.split(".")
    for cut in range(len(parts) - 1, 0, -1):
        try:
            found: Any = importlib.import_module(".".join(parts[:cut]))
        except ImportError:
            continue
        try:
            for attribute in parts[cut:]:
                found = getattr(found, attribute)
        except AttributeError:
            continue
        return found
    raise ValueError(f"nothing is named {name}")


def _pattern_of(argument: str, base: str) -> tuple[str, int]:
    """Intent:
        The Python regular expression and flags a canonical argument states, to be read under
        the word's predicate: a literal escaped, a `re(...)` call's own, a shape's equivalent
        expression over the base (`ascii` or, for any other base, `unicode`), or those of the
        compiled pattern or `Shape` a dotted name names.

    Raises:
        ValueError: the argument does not read, or the name is of neither kind of object.
    """
    literal = _string(argument)
    if literal is not None:
        return re.escape(literal), 0
    pattern = read_re(argument)
    if pattern is not None:
        return pattern
    over = base if base in SHAPE else "unicode"
    parts = _shape_call(argument)
    if parts is not None:
        return read_shape(parts, over).pattern, 0
    found = _object(argument)
    if isinstance(found, re.Pattern) and isinstance(found.pattern, str):
        return found.pattern, int(found.flags) & ~int(re.UNICODE)
    if isinstance(found, Shape):
        return found.pattern, 0
    raise ValueError(f"{argument} names {type(found).__name__}, not a compiled pattern or a Shape")


def _star_set(doc: dict[str, Any]) -> Any:
    """Intent:
        The character set of a term that is exactly every string over one set, as ranges, or
        None for any other term.
    """
    node = doc.get("language")
    if not doc.get("exact") or not isinstance(node, dict) or node.get("op") != "repeat" \
            or node["min"] != 0 or node["max"] is not None:
        return None
    arg = node["arg"]
    if arg["op"] == "chars":
        return tuple((lo, hi) for lo, hi in arg["ranges"])
    if arg["op"] == "literal" and len(arg["codes"]) == 1:
        return ((arg["codes"][0], arg["codes"][0]),)
    return None


def _cut_to(node: dict[str, Any], over: Any) -> dict[str, Any] | None:
    """Intent:
        The node with every character set cut to the set `over`, which holds the same strings
        over `over` as the node does; None for a node with a complement, whose strings over
        `over` are not found this way.
    """
    op = node["op"]
    if op in ("empty", "epsilon"):
        return node
    if op == "chars":
        kept = _algebra._cs_inter(tuple((lo, hi) for lo, hi in node["ranges"]), over)
        return _algebra.canonical({"op": "chars", "ranges": [[lo, hi] for lo, hi in kept]})
    if op == "literal":
        inside = all(_algebra._cs_has(over, code) for code in node["codes"])
        return node if inside else {"op": "empty"}
    if op == "complement":
        return None
    if op == "repeat":
        arg = _cut_to(node["arg"], over)
        return None if arg is None else _algebra.canonical({**node, "arg": arg})
    args = [_cut_to(arg, over) for arg in node["args"]]
    return None if None in args else _algebra.canonical({"op": op, "args": args})


def _inter(a: dict[str, Any], b: dict[str, Any], negate: bool) -> dict[str, Any]:
    """Intent:
        The term of the texts in the term `a` and in the term `b`, or, with `negate`, in `a`
        and not in `b`. Exact when both are; otherwise a pair, in which `at_least` meets the
        widest reading of each side and `at_most` the narrowest (the complement of a bound
        being a bound the other way). Where `a` is every string over one character set, `b` is
        first cut to that set, so bounds that differ only outside it become one exact term.
    """
    def side(doc: dict[str, Any], bound: str) -> dict[str, Any]:
        node: dict[str, Any] = doc["language"] if "language" in doc else doc[bound]
        return node

    def meet(bound: str) -> dict[str, Any]:
        other = {"at_least": "at_most", "at_most": "at_least"}[bound]
        right = {"op": "complement", "arg": side(b, other)} if negate else side(b, bound)
        return _algebra.canonical({"op": "inter", "args": [side(a, bound), right]})

    over = _star_set(a)
    if over is not None:
        cut = {key: _cut_to(b[key], over) for key in ("language", "at_least", "at_most") if key in b}
        if None not in cut.values():
            b = {**b, **{key: node for key, node in cut.items() if node is not None}}
            if "language" not in b and b["at_least"] == b["at_most"]:
                b = {"exact": True, "language": b["at_least"],
                     **{k: v for k, v in b.items() if k not in ("exact", "at_least", "at_most")}}
    exact = bool(a.get("exact")) and bool(b.get("exact"))
    doc: dict[str, Any] = {"kind": "regular_language", "version": _algebra.TERM_VERSION,
                           "alphabet": a["alphabet"], "exact": exact}
    if exact:
        doc["language"] = meet("at_least")
    else:
        doc["at_least"], doc["at_most"] = meet("at_least"), meet("at_most")
    causes = [*a.get("source", {}).get("not_exact", []), *b.get("source", {}).get("not_exact", [])]
    doc["source"] = {"dialect": "refined", "of": [a.get("source", {}), b.get("source", {})],
                     "negated": negate, **({"not_exact": causes} if causes else {})}
    return doc


def narrowed(base: Any, inner: Any, said: str, negated: bool) -> TextLanguage:
    """Intent:
        The members of the text language `base` that are in `inner` (or, with `negated`, are
        not), named `base, said`. Membership is both languages' own; draws are `inner`'s kept
        where `base` admits them, then `base`'s kept where the predicate holds; hazards are
        those of either that are members; `outside` is a member of `base` on the other side
        of the predicate. Where both state a `definition`, so does the result: the terms met.
    """
    def accepts(text: str) -> bool:
        return bool(base.contains(text)) and bool(inner.contains(text)) != negated

    def draw(rng: random.Random) -> str:
        for source in ((inner, base) if not negated else (base,)):
            for _ in range(60):
                try:
                    text = source.sample(rng)
                except ValueError:
                    break
                if isinstance(text, str) and accepts(text):
                    return text
        for hazard in (*inner.hazards(), *base.hazards()):
            if isinstance(hazard.value, str) and accepts(hazard.value):
                return str(hazard.value)
        raise ValueError(f"no member of L[{base.name}, {said}] was drawn")

    def other_side(rng: random.Random) -> Any:
        for source in ((base, inner) if not negated else (inner, base)):
            for _ in range(60):
                try:
                    text = source.sample(rng)
                except ValueError:
                    break
                if isinstance(text, str) and base.contains(text) and not accepts(text):
                    return text
        return base.outside(rng)

    schema: dict[str, Any] = {}
    ours, theirs = base.to_json().get("definition"), inner.to_json().get("definition")
    if isinstance(ours, dict) and isinstance(theirs, dict):
        schema["definition"] = _inter(ours, theirs, negated)
    hazards = tuple(h for h in (*inner.hazards(), *getattr(base, "extra_hazards", ()))
                    if isinstance(h.value, str))
    return _Narrowed(f"{base.name}, {said}", level="predicate", accepts=accepts, generate=draw,
                     pool=getattr(base, "pool", "a") or "a", schema=schema, extra_hazards=hazards,
                     other_side=other_side)


@dataclass(frozen=True)
class _Narrowed(TextLanguage):
    """A base text language under a predicate; `other_side` draws a
    member of the base the predicate refuses."""
    other_side: Any = None

    def outside(self, rng: random.Random) -> Any:
        found = self.other_side(rng) if self.other_side is not None else None
        return found if found is None or not self.contains(found) else None


def _root(language: Any) -> Any:
    """Intent:
        The language beneath any measure refinements of `language`.
    """
    while getattr(language, "base", None) is not None and hasattr(language.base, "contains"):
        language = language.base
    return language


def _is_text(language: Any) -> bool:
    """Intent:
        Whether a language is of text: its members are strings.
    """
    return getattr(language, "kind", None) == "string"


def _pattern_language_of(argument: str, word: str, base: str) -> Any:
    """Intent:
        The language of the strings a pattern word holds of, for one canonical argument read
        over the base: the pattern's own, for every supported Python or, where the argument
        pins a version (`re(r"...", python 3.13)`), for that Python alone.

    Raises:
        ValueError: the argument does not read.
    """
    pattern, flags = _pattern_of(argument, base)
    return _regular.pattern_language(pattern, word, flags, version=_re_version(argument))


def _said(word: str, arguments: tuple[str, ...], negated: bool) -> str:
    """Intent:
        A predicate as text: `word (arguments)`, with `not` in front when negated.
    """
    return ("not " if negated else "") + f"{word} ({', '.join(arguments)})"


def _pattern_word(word: str, sugar: tuple[str, ...]) -> Any:
    """Intent:
        The registry record of one pattern word, or None on a mathema with no word registry.
    """
    def arguments(given: tuple[str, ...], operator: str | None) -> tuple[str, ...]:
        if len(given) != 1:
            raise ValueError(f'{word} takes one argument, a pattern: {word} (re(r"[a-z]+", python))')
        return (canonical_pattern_argument(given[0], operator),)

    def refine(language: Any, given: tuple[str, ...], negated: bool = False) -> Any:
        found = _pattern_language_of(given[0], word, str(getattr(_root(language), "name", "")))
        return narrowed(language, found, _said(word, tuple(given), negated), negated)

    def suggest(base: str | None, given: tuple[str, ...]) -> str | None:
        try:
            said = arguments(tuple(given), None)
        except ValueError:
            return None
        return f"L[unicode, {_said(word, said, False)}]"

    def reads_call(callee: Any) -> tuple[str, ...] | None:
        method = PATTERN_WORDS[word]
        owner, name = getattr(callee, "__self__", None), getattr(callee, "__name__", None)
        pattern: Any = None
        flags = 0
        if isinstance(owner, re.Pattern) and name == method:
            pattern, flags = owner.pattern, int(owner.flags) & ~int(re.UNICODE)
        elif isinstance(callee, functools.partial) and method is not None \
                and callee.func is getattr(re, method) and callee.args:
            first = callee.args[0]
            if isinstance(first, re.Pattern):
                pattern, flags = first.pattern, int(first.flags) & ~int(re.UNICODE)
            else:
                pattern = first
                flags = int(callee.keywords.get("flags", callee.args[1] if len(callee.args) > 1 else 0))
        if not isinstance(pattern, str):
            return None
        try:
            return (re_text(pattern, flags),)
        except ValueError:
            return None

    if PredicateWord is None:
        return None
    example = f'L[unicode, {word} (re(r"[a-z]+", python))]'
    return PredicateWord(  # type: ignore[operator]
        word, refine, sugar=sugar, arguments=arguments, applies=_is_text, kinds=("text",),
        examples={"text": example}, suggest=suggest,
        **({"reads_call": reads_call} if _has_reads_call() else {}))


def _has_reads_call() -> bool:
    """Intent:
        Whether mathema's word record takes a `reads_call` function.
    """
    import dataclasses
    return PredicateWord is not None and any(
        f.name == "reads_call" for f in dataclasses.fields(PredicateWord))  # type: ignore[arg-type]


def _strings(given: tuple[str, ...], word: str, example: str) -> tuple[str, ...]:
    """Intent:
        The strings the quoted arguments state.

    Raises:
        ValueError: an argument is not a quoted string.
    """
    out = []
    for argument in given:
        value = _string(argument)
        if value is None:
            raise ValueError(f"{word} takes quoted arguments, {example}, not {argument!r}")
        out.append(value)
    return tuple(out)


def _within_word() -> Any:
    """Intent:
        The registry record of `within`, or None on a mathema with no word registry.
    """
    example = 'within ("/workspace")'

    def arguments(given: tuple[str, ...], operator: str | None) -> tuple[str, ...]:
        if not given:
            raise ValueError(f"within takes at least one argument: {example}")
        return tuple(_quoted(value) for value in _strings(tuple(given), "within", example))

    def applies(language: Any) -> bool:
        kind = WITHIN.get(str(getattr(_root(language), "name", "")))
        return kind is not None and kind.registered

    def refine(language: Any, given: tuple[str, ...], negated: bool = False) -> Any:
        base = str(_root(language).name)
        regions = _strings(tuple(given), "within", example)
        refusal = within_refusal(base, regions)
        if refusal is not None:
            meant = suggest_within(base, regions)
            raise ValueError(refusal + (f". Did you mean {meant[0]}?" if meant else ""))
        inside = WITHIN[base].build(*regions)
        if negated or _root(language) is not language:
            return narrowed(language, inside, _said("within", tuple(given), negated), negated)
        return inside

    def suggest(base: str | None, given: tuple[str, ...]) -> str | None:
        try:
            regions = _strings(tuple(given), "within", example)
        except ValueError:
            return None
        meant = suggest_within(base or "unicode", regions)
        return meant[0] if meant else None

    if PredicateWord is None:
        return None
    kinds = tuple(kind.noun for kind in WITHIN.values() if kind.registered)
    examples = {WITHIN[base].noun: text for base, text in within_examples().items()}
    return PredicateWord(  # type: ignore[operator]
        "within", refine, keyword=True, arguments=arguments, applies=applies, kinds=kinds,
        examples=examples, suggest=suggest)


def _shape_word() -> Any:
    """Intent:
        The registry record of `shape`, or None on a mathema with no word registry.
    """
    def arguments(given: tuple[str, ...], operator: str | None) -> tuple[str, ...]:
        shape = read_shape(list(given))
        return (_quoted(shape.shape), *(f"{symbol} = {found.text}" for symbol, found in shape.bindings))

    def applies(language: Any) -> bool:
        return str(getattr(_root(language), "name", "")) in SHAPE

    def refine(language: Any, given: tuple[str, ...], negated: bool = False) -> Any:
        inside = shape_language(read_shape(list(given), str(_root(language).name)))
        if negated or _root(language) is not language:
            return narrowed(language, inside, _said("shape", tuple(given), negated), negated)
        return inside

    def suggest(base: str | None, given: tuple[str, ...]) -> str | None:
        picture = _string(given[0]) if given else None
        if picture is None:
            return None
        try:
            bound = _bindings(list(given[1:]))
        except ValueError:
            return None
        meant = suggest_shape(base or "unicode", (picture,), bound)
        return meant[0] if meant else None

    if PredicateWord is None:
        return None
    return PredicateWord(  # type: ignore[operator]
        "shape", refine, arguments=arguments, applies=applies,
        kinds=tuple(f"text in L[{base}]" for base in SHAPE),
        examples={f"text in L[{base}]": text for base, text in shape_examples().items()},
        suggest=suggest)


def _alphabet_of(pieces: Any) -> Alphabet:
    """Intent:
        The alphabet of `("name", name)` and `("char", character)` pieces.

    Raises:
        ValueError: a name is not a named alphabet (the nearest is offered), or a piece is of
            neither kind.
    """
    names, characters = [], []
    for kind, value in pieces:
        if kind == "name":
            if value not in NAMES:
                near = difflib.get_close_matches(str(value), NAMES, n=1)
                raise ValueError(f"{value!r} is not a named alphabet ({', '.join(NAMES)})"
                                 + (f". Did you mean {near[0]}?" if near else ""))
            names.append(value)
        elif kind == "char" and isinstance(value, str) and len(value) == 1:
            characters.append(value)
        else:
            raise ValueError(f"an alphabet is named alphabets and single characters, not {value!r}")
    return Alphabet(tuple(names), tuple(characters))


def build_alphabet(pieces: Any) -> Any:
    """Intent:
        The language an alphabet expression heads: every string over the union of its named
        alphabets and characters.

    Raises:
        ValueError: a piece is refused, with the nearest named alphabet for a name that is
            not one.
    """
    return alphabet_language(_alphabet_of(pieces))


def order_alphabet(pieces: Any) -> tuple[tuple[str, str], ...]:
    """Intent:
        The pieces in the order canonical text writes them: named alphabets in the order of
        `NAMES` (a name that is not one after them, as written), then characters by code
        point, each piece once.
    """
    kept = list(dict.fromkeys((str(kind), str(value)) for kind, value in pieces))
    names = [p for p in kept if p[0] == "name"]
    known = sorted((p for p in names if p[1] in NAMES), key=lambda p: NAMES.index(p[1]))
    unknown = [p for p in names if p[1] not in NAMES]
    characters = sorted((p for p in kept if p[0] != "name"), key=lambda p: [ord(c) for c in p[1]])
    return (*known, *unknown, *characters)


MATCHES = _pattern_word("matches", ("in", "=="))
CONTAINS = _pattern_word("contains", ("*=",))
STARTS_WITH = _pattern_word("starts with", ("^=",))
ENDS_WITH = _pattern_word("ends with", ("$=",))
WITHIN_WORD = _within_word()
SHAPE_WORD = _shape_word()
ALPHABET = None if AlphabetConstructor is None else AlphabetConstructor(  # type: ignore[operator]
    build=build_alphabet, order=order_alphabet)

#: every word record this package registers, by its word
WORDS = {record.word: record for record in (MATCHES, CONTAINS, STARTS_WITH, ENDS_WITH, WITHIN_WORD,
                                            SHAPE_WORD) if record is not None}

#: DRAFT, names awaiting sign-off: one worked claim for each language, predicate word and
#: constructor the package newly registers, by entry-point key, in canonical text. They are
#: not in the package's lexicon: a predicate row parses only on a mathema with the word registry.
DRAFT_ROWS: dict[str, str] = {
    "lower": "for s in L[lower], f(s) = s",
    "upper": "for s in L[upper], f(s) = s",
    "matches": 'for s in L[unicode, matches (re(r"[a-z0-9]+(?:-[a-z0-9]+)*", python))], f(s) = s',
    "contains": 'for s in L[unicode, contains ("://")], f(s) = s',
    "starts_with": 'for s in L[unicode, starts with ("http://")], f(s) = s',
    "ends_with": 'for s in L[unicode, ends with (".json")], f(s) = s',
    "within": 'for p in L[path, within ("/workspace")], f(p) = p',
    "shape": 'for s in L[ascii, shape ("AA99[ ]9AA")], f(s) = s',
    "alphabet": 'for s in L[lower + digit + "_"], f(s) = s',
}

__all__ = ["ALPHABET", "CONTAINS", "DIALECTS", "ENDS_WITH", "FLAGS", "MATCHES", "PATTERN_WORDS",
           "RESERVED", "SHAPE_WORD", "STARTS_WITH", "UNAVAILABLE", "WITHIN_WORD", "WORDS",
           "build_alphabet", "canonical_pattern_argument", "narrowed", "order_alphabet", "re_text",
           "read_re", "read_shape", "shape_text", "version_pin"]
