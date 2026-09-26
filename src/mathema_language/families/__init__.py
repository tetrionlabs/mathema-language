# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The hazard families over text, registered under mathema's
`mathema.claim_families` group so `is_length_safe(s)` and
`is_encoding_safe(s)` parse and adjudicate like mathema's own members.

Each reads the language the target is declared over (`for s in
L[ascii]`), or every `str` when none is declared, and feeds the target
the language's own hazards of the kind the family is about. An
ACCIDENTAL crash, an exception type the body never raises itself, on a
member with no rejection is the falsification, with the input shrunk
to a minimal witness that stays inside the language; a deliberate
rejection (a `ValueError` the body raises) or a clean return holds.
Sampling never proves.
"""
from __future__ import annotations

import ast
import random
import unicodedata
from collections.abc import Callable
from typing import Any

from .._surface import (
    LanguageRef,
    OutputPredicateFamily,
    SafetyFamily,
    call_with_target,
    format_point,
    pinned_float_env,
    probe_trials,
    resolve_language,
    sample_bound,
    shrink,
)
from ..text import UNICODE, adapt

#: the exception types that signal a crash rather than a rejection;
#: the same seven mathema's own fuzz family counts, pinned against it
#: by the integration test
ACCIDENTAL_CRASHES: tuple[type[BaseException], ...] = (
    TypeError, IndexError, UnicodeError, RecursionError, AttributeError,
    KeyError, OverflowError)

_LONG = 65536


def _languages(domain: dict[str, Any], target: str) -> tuple[str, list[Any]]:
    """`(names, languages)` the target is declared over, or the unicode
    language when the claim declares none."""
    bound = domain.get(target)
    if bound is None or getattr(bound, "base_type", None) != "L":
        return "unicode", [UNICODE]
    refs = [piece for piece in bound.pieces if isinstance(piece, LanguageRef)]
    return " | ".join(ref.name for ref in refs), [resolve_language(ref) for ref in refs]


def _contains(languages: list[Any], value: object) -> bool:
    return any(language.contains(value) for language in languages)


def _hazard_values(languages: list[Any], kinds: tuple[str, ...] | None = None) -> list[str]:
    """The hazard members of `languages`, of `kinds` or of every kind,
    each once, in corpus order."""
    out: list[str] = []
    seen: set[str] = set()
    for language in languages:
        for hazard in language.hazards():
            if (kinds is None or hazard.kind in kinds) and hazard.value not in seen:
                seen.add(hazard.value)
                out.append(hazard.value)
    return out


def _raised_by_the_body(tree: ast.AST | None) -> frozenset[str]:
    """The exception type names the body raises on purpose, which are
    then rejections rather than crashes when they arrive."""
    if tree is None:
        return frozenset()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise) and node.exc is not None:
            exc = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
            if isinstance(exc, ast.Name):
                names.add(exc.id)
    return frozenset(names)


def _codecs_named(tree: ast.AST | None) -> list[str]:
    """The codec names the body encodes or decodes with, as written."""
    if tree is None:
        return []
    out: list[str] = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("encode", "decode") and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            out.append(node.args[0].value)
    return out


#: a member each codec cannot encode, the boundary the family visits
_CODEC_BOUNDARIES: dict[str, str] = {
    "ascii": "\x80", "us-ascii": "\x80", "latin-1": "Ā",
    "latin1": "Ā", "iso-8859-1": "Ā", "cp1252": "Ā",
    "utf-8": "\ud800", "utf8": "\ud800", "utf-16": "\ud800",
    "utf-32": "\ud800",
}


def _decline(fn: Any, facts: Any, lhs_src: str, rhs_src: str, relation: str,
             domain: dict[str, Any] | None = None,
             tolerance: float | None = None) -> None:
    """The structural half of both members: nothing about a crash on a
    hazard input is established symbolically, so the trials decide."""
    return None


def _string_params(fn: Any, facts: Any) -> set[str]:
    """The suggestion gate: every parameter the body treats as text."""
    return {p for p in facts.params if facts.param_kinds.get(p) == "string"}


def _describe(value: str) -> str:
    """A member for a witness: its repr and, for a single character,
    its Unicode name and category."""
    if len(value) == 1:
        name = unicodedata.name(value, "unnamed")
        return f"{value!r} ({name}, category {unicodedata.category(value)})"
    if len(value) > 40:
        return f"{value[:20]!r}... ({len(value)} characters)"
    return repr(value)


def _probe_over(kinds: tuple[str, ...], extra: Callable[..., list[str]],
                crashes: tuple[type[BaseException], ...],
                what: str) -> Callable[..., Any]:
    """Build a probe half feeding the target the language's hazards of
    `kinds` plus `extra(languages, facts)` members, counting `crashes`
    the body does not raise itself as falsifications."""

    def probe(fn: Any, facts: Any, cj: Any, domain: dict[str, Any],
              rng: random.Random, trials: int) -> Any:
        target = cj.lhs
        if target not in facts.params:
            return None
        names, languages = _languages(domain, target)
        deliberate = _raised_by_the_body(facts.tree)
        counted = tuple(t for t in crashes if t.__name__ not in deliberate)
        corpus = _hazard_values(languages, kinds)
        seen = set(corpus)
        for value in extra(languages, facts):
            if value not in seen and _contains(languages, value):
                seen.add(value)
                corpus.append(value)
        if not corpus:
            return ("skipped", 0, f"L[{names}] has no {what} hazard to try")

        def crash_on(args: list[Any], value: str) -> str | None:
            try:
                with pinned_float_env():
                    call_with_target(fn, facts, target, args, value)
            except counted as exc:
                return type(exc).__name__
            except Exception:
                return None
            return None

        state = {"i": 0}

        def trial(args: list[Any]) -> Any:
            if state["i"] >= len(corpus):
                return True
            value = corpus[state["i"]]
            state["i"] += 1
            exc = crash_on(args, value)
            if exc is None:
                return True
            minimal = shrink(value, lambda s: crash_on(args, s) is not None
                             and _contains(languages, s))
            return (f"{target} = {_describe(minimal)} (inside L[{names}]) "
                    f"raised {exc} on a {what} hazard, an unguarded crash, "
                    f"not a declared rejection")

        return probe_trials(fn, facts, target, domain, rng,
                            max(trials, len(corpus)), trial)

    return probe


def _long_members(languages: list[Any], facts: Any) -> list[str]:
    """A sixty-four kibibyte member of each language, from its own
    first pool character."""
    out: list[str] = []
    for language in languages:
        pool = getattr(language, "pool", "") or ""
        if pool:
            out.append(pool[0] * _LONG)
    return out


def _codec_boundaries(languages: list[Any], facts: Any) -> list[str]:
    """The member past each codec boundary the body names."""
    return [_CODEC_BOUNDARIES[codec.lower()]
            for codec in _codecs_named(facts.tree)
            if codec.lower() in _CODEC_BOUNDARIES]


#: `is_length_safe(s)`: the long and pathological members of the
#: language (an overlong string, deep nesting, a backtracking shape)
#: reach the body without an accidental crash
LENGTH_SAFE = SafetyFamily(
    "is_length_safe", derive=_decline,
    probe=_probe_over(("length",), _long_members, ACCIDENTAL_CRASHES, "length"),
    suggest_targets=_string_params, probe_route="probe:minimal_example")

#: `is_encoding_safe(s)`: the control and format code points, the
#: combining marks, the surrogates, the characters that change under
#: case or normalisation, and the member past every codec boundary the
#: body names, reach the body without an accidental crash
ENCODING_SAFE = SafetyFamily(
    "is_encoding_safe", derive=_decline,
    probe=_probe_over(("control", "encoding"), _codec_boundaries,
                      ACCIDENTAL_CRASHES, "encoding"),
    suggest_targets=_string_params, probe_route="probe:minimal_example")



def _return_hint(fn: Any) -> object | None:
    """The function's return annotation, resolved when it can be."""
    import typing

    try:
        return typing.get_type_hints(fn).get("return")
    except Exception:
        return getattr(fn, "__annotations__", {}).get("return")


def _target_language(fn: Any, facts: Any, domain: dict[str, Any]) -> tuple[str, list[Any], str]:
    """`(names, languages, how)` the output is held to: the language
    the first text parameter is declared over, else the return
    annotation through the text adaptor, else every `str`."""
    for p in facts.params:
        bound = domain.get(p)
        if bound is not None and getattr(bound, "base_type", None) == "L":
            refs = [piece for piece in bound.pieces if isinstance(piece, LanguageRef)]
            if refs:
                return (" | ".join(ref.name for ref in refs),
                        [resolve_language(ref) for ref in refs],
                        f"the language {p} is declared over")
    hint = _return_hint(fn)
    if hint is not None:
        language = adapt(hint)
        if language is not None:
            hint_text = getattr(hint, "__name__", None) or str(hint)
            return language.name, [language], f"the return annotation {hint_text}"
    return "unicode", [UNICODE], "no declared language, so every str"


def _explained(languages: list[Any], value: object) -> str:
    """The first language's account of why `value` is not a member,
    parenthesised, or nothing."""
    for language in languages:
        try:
            why = language.explain(value)
        except Exception:
            continue
        if why:
            return f" ({why})"
    return ""


def _output_in_language_probe(fn: Any, facts: Any, cj: Any, domain: dict[str, Any] | None,
                              rng: random.Random, trials: int) -> Any:
    """Feed the first parameter its declared language's hazards, then
    draws; every output must be a member of the target language."""
    domain = domain or {}
    if not facts.params:
        return None
    names, languages, how = _target_language(fn, facts, domain)
    target = facts.params[0]
    bound = domain.get(target)
    lead: list[str] = []
    if bound is not None and getattr(bound, "base_type", None) == "L":
        lead = _hazard_values([resolve_language(piece) for piece in bound.pieces
                               if isinstance(piece, LanguageRef)])
    state = {"i": 0}
    where = facts.params.index(target)

    def trial(args: list[Any]) -> Any:
        filled = list(args)
        if state["i"] < len(lead):
            filled[where] = lead[state["i"]]
            state["i"] += 1
        else:
            filled[where] = sample_bound(bound, rng, facts.param_kinds.get(target, "scalar"))
        try:
            with pinned_float_env():
                out = fn(*filled)
        except Exception:
            return None
        if _contains(languages, out):
            return True
        return (f"{format_point(tuple(filled))}: output {out!r} is not in "
                f"L[{names}], the target from {how}{_explained(languages, out)}")

    return probe_trials(fn, facts, target, domain, rng, max(trials, len(lead)), trial)


class _OutputInLanguage(OutputPredicateFamily):
    """`output_in_language(f(s))`: every output is a member of the
    target language, which is the language the first text parameter is
    declared over (closure: a slug in, a slug out), else the language
    the return annotation adapts to, else every `str`. The witness
    names the target and how it was chosen."""

    def __init__(self) -> None:
        super().__init__("output_in_language", lambda out: None)

    def routes(self) -> dict[str, Any]:
        return {"probe:algorithmic": _output_in_language_probe}


OUTPUT_IN_LANGUAGE = _OutputInLanguage()

__all__ = ["ACCIDENTAL_CRASHES", "ENCODING_SAFE", "LENGTH_SAFE", "OUTPUT_IN_LANGUAGE"]
