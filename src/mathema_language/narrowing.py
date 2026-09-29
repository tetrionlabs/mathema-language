# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Narrowing a language to what a function accepts.

A function that refuses an input (raises one of the errors that mean
"not for me", `ValueError` unless told otherwise) is stating its domain.
A claim over a language holding such inputs is falsified, because the
language is wider than the function's domain; `refused_inputs` shows
which members are refused, and `narrow_language` returns the language
without them, to be named in the claim by its dotted path
(`L[myapp.UPLOAD_NAMES]`). Any other exception is a crash, never a
refusal: `refused_inputs` lets it propagate, and the narrowed language
keeps the input, so a claim over it still finds the crash.
"""
from __future__ import annotations

import random
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from ._surface import Problem

#: how many base draws a sample or an outside draw tries before giving up
_TRIES = 200


@dataclass(frozen=True)
class Refusal:
    """One refused input: the value, the name of the error raised, and
    its message."""
    value: Any
    error: str
    message: str


def _call(fn: Callable[[Any], Any], value: Any,
          errors: tuple[type[BaseException], ...]) -> BaseException | None:
    """The refusal `fn` raises at `value`, or None when it returns."""
    try:
        fn(value)
    except errors as e:
        return e
    return None


def _key(value: Any) -> str:
    return f"{type(value).__name__}:{value!r}"


def refused_inputs(fn: Callable[[Any], Any], language: Any, *,
                   errors: tuple[type[BaseException], ...] = (ValueError,),
                   draws: int = 200, seed: int = 0) -> list[Refusal]:
    """Every distinct member of `language` that `fn` refuses, from the
    language's hazards and then `draws` random members, in the order
    found. An input is refused when `fn` raises one of `errors`; any
    other exception propagates, as a crash, not a refusal."""
    rng = random.Random(seed)
    candidates = [h.value for h in language.hazards()]
    candidates += [language.sample(rng) for _ in range(draws)]
    found: dict[str, Refusal] = {}
    for value in candidates:
        if _key(value) in found:
            continue
        refusal = _call(fn, value, errors)
        if refusal is not None:
            found[_key(value)] = Refusal(value, type(refusal).__name__, str(refusal))
    return list(found.values())


class NarrowedLanguage:
    """The members of `base` that `fn` accepts: membership is the base's,
    then a call of `fn` that raises none of `errors` (a crash keeps the
    input a member). Random members come from the base by rejection; the
    hazards are the base's accepted ones; the outside draw is a refused
    base member where one is known, else the base's own."""

    def __init__(self, base: Any, fn: Callable[[Any], Any], *,
                 errors: tuple[type[BaseException], ...] = (ValueError,),
                 name: str | None = None) -> None:
        self.base = base
        self.fn = fn
        self.errors = tuple(errors)
        self.name = name or f"{base.name}, accepted by {getattr(fn, '__name__', fn)}"
        self.kind = base.kind
        self.level = "predicate"
        self._refused: list[Any] | None = None

    def _refusal(self, value: Any) -> BaseException | None:
        try:
            return _call(self.fn, value, self.errors)
        except Exception:
            return None

    def contains(self, value: Any) -> bool:
        return bool(self.base.contains(value)) and self._refusal(value) is None

    def explain(self, value: Any) -> list[Problem] | None:
        problems: list[Problem] | None = self.base.explain(value)
        if problems:
            return problems
        refusal = self._refusal(value)
        if refusal is None:
            return None
        return [Problem("", f"accepted by {getattr(self.fn, '__name__', self.fn)} "
                            f"(refused: {type(refusal).__name__}: {refusal})", value)]

    def sample(self, rng: random.Random) -> Any:
        for _ in range(_TRIES):
            value = self.base.sample(rng)
            if self._refusal(value) is None:
                return value
        raise ValueError(f"L[{self.name}]: no accepted member in {_TRIES} draws")

    def members(self, limit: int) -> tuple[Any, ...] | None:
        every = self.base.members(limit)
        if every is None:
            return None
        return tuple(v for v in every if self._refusal(v) is None)

    def hazards(self) -> tuple[Any, ...]:
        return tuple(h for h in self.base.hazards() if self._refusal(h.value) is None)

    def _refused_members(self) -> list[Any]:
        if self._refused is None:
            self._refused = [h.value for h in self.base.hazards()
                             if self._refusal(h.value) is not None]
        return self._refused

    def outside(self, rng: random.Random) -> Any:
        refused = self._refused_members()
        if refused:
            return rng.choice(refused)
        return self.base.outside(rng)

    def shrink(self, value: Any) -> Iterator[Any]:
        return (v for v in self.base.shrink(value) if self._refusal(v) is None)

    def fields(self) -> dict[str, Any] | None:
        fields: dict[str, Any] | None = self.base.fields()
        return fields

    def render(self, ascii_mode: bool = True) -> str:
        return f"L[{self.name}]"

    def to_json(self) -> dict[str, Any]:
        out = dict(self.base.to_json())
        out["x-accepted-by"] = f"{getattr(self.fn, '__module__', '')}.{getattr(self.fn, '__qualname__', self.fn)}"
        return out


def narrow_language(language: Any, fn: Callable[[Any], Any], *,
                    errors: tuple[type[BaseException], ...] = (ValueError,),
                    name: str | None = None) -> NarrowedLanguage:
    """`language` without the inputs `fn` refuses, where a refusal is a
    raise of one of `errors`. Assign it in a module and name it in a claim
    by its dotted path: `UPLOAD_NAMES = narrow_language(UNICODE,
    get_valid_filename, errors=(SuspiciousFileOperation,))`, then
    `for name in L[myapp.UPLOAD_NAMES], ...`."""
    return NarrowedLanguage(language, fn, errors=errors, name=name)


__all__ = ["NarrowedLanguage", "Refusal", "narrow_language", "refused_inputs"]
