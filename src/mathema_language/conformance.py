# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Conformance checks for row adaptors, for an adaptor's own tests to
call with one of its schema objects. The package's own adaptors pass
them in this package's tests.

`record_adaptor_problems(obj)` lists every way the record language of
`obj` falls short, empty when there is none. It checks that an adaptor in the registry returns a language for `obj`
(or that the `adapt` given does, and the registry agrees unless
`registered=False`), that the language satisfies mathema's `Language`
protocol and has kind `row`, that every hazard and `samples` random
members are members by the library's own validator; `outside` never draws a member and its
explanation's paths follow the path grammar (`""` the value, `.col` a
field, `[i]` an item, composed); every shrink of a member is a member;
and `fields()` is `None` or maps field names to a bound mathema's
derive lift reads (`"Z"`, `"R"`, `"N"`, an interval, a domain, a
`LanguageRef`) or `None`. `foreign_object_problems(adapt)` checks the
other half of the contract: the adaptor returns `None` for objects that
are not its own, without importing any module outside the standard
library, mathema and the adaptor's own package."""
from __future__ import annotations

import random
import re
import sys
from collections.abc import Callable
from typing import Any

from ._surface import LanguageRef, domain_bound_from_json, language_problems
from .schema.adaptors import adapt_row

#: an explanation path: fields and items, composed
_PATH = re.compile(r"^(\.[A-Za-z_][A-Za-z0-9_]*|\[\d+\])*$")

_BOUND_TYPES = (
    type(domain_bound_from_json({"lo": 0.0, "hi": 1.0, "closed_lo": True, "closed_hi": True})),
    type(domain_bound_from_json({"base_type": "Z", "excluded": [], "explicit_type": True,
                                 "pieces": [{"lo": 0.0, "hi": 1.0,
                                             "closed_lo": True, "closed_hi": True}]})),
    LanguageRef,
)


def _validator(language: Any) -> Callable[[Any], list[Any]]:
    """The ecosystem's own validator where the language exposes one,
    else the language's own membership as a one-problem list."""
    ecosystem, schema = getattr(language, "ecosystem", None), getattr(language, "schema", None)
    if ecosystem is not None and schema is not None and hasattr(ecosystem, "validate_row"):
        return lambda value: list(ecosystem.validate_row(schema, value))
    return lambda value: [] if language.contains(value) else ["not a member"]


def _fields_problems(language: Any) -> list[str]:
    try:
        fields = language.fields()
    except Exception as e:
        return [f"fields() raised {e!r}"]
    if fields is None:
        return []
    if not isinstance(fields, dict):
        return [f"fields() returned {type(fields).__name__}, not a dict or None"]
    out = []
    names = {f.name for f in getattr(getattr(language, "schema", None), "fields", ())}
    for name, bound in fields.items():
        if not isinstance(name, str):
            out.append(f"fields(): key {name!r} is not a field name")
        elif names and name not in names:
            out.append(f"fields(): {name!r} is not a field of the schema")
        if bound is None or bound in ("Z", "R", "N") or isinstance(bound, _BOUND_TYPES):
            continue
        out.append(f"fields(): {name!r} maps to {bound!r}, which the derive lift cannot read")
    return out


def record_adaptor_problems(obj: Any, *, adapt: Callable[[Any], Any] | None = None,
                         registered: bool = True, samples: int = 50,
                         outside_draws: int = 20, seed: int = 0) -> list[str]:
    """Every way the row language of `obj` fails the adaptor contract,
    empty when there is none. With `adapt` the adaptor is called
    directly and, unless `registered` is False, the registry must
    return the same kind of language for `obj`; without `adapt`, the
    registry alone is asked."""
    check_registry = registered or adapt is None
    from_registry = adapt_row(obj) if check_registry else None
    language = adapt(obj) if adapt is not None else from_registry
    if language is None:
        return [f"no adaptor returns a record language for {obj!r}"]
    out = [f"Language protocol: {p}" for p in language_problems(language)]
    if getattr(language, "kind", None) != "row":
        out.append(f"kind is {getattr(language, 'kind', None)!r}, not 'row'")
    if check_registry and from_registry is None:
        out.append("no registered adaptor returns a language for the object; register the adaptor "
                   "under mathema.language_adaptors")
    elif check_registry and (
            type(from_registry) is not type(language)
            or type(getattr(from_registry, "ecosystem", None))
            is not type(getattr(language, "ecosystem", None))):
        out.append(f"the registry returns {from_registry!r}, not {language!r}: "
                   f"another adaptor is asked first; raise this adaptor's priority")
    if out:
        return out
    validate = _validator(language)
    rng = random.Random(seed)
    for hazard in language.hazards():
        problems = validate(hazard.value)
        if problems:
            out.append(f"hazard {hazard.note!r} is not a member: {problems}")
    members = []
    for i in range(samples):
        try:
            value = language.sample(rng)
        except Exception as e:
            out.append(f"sample {i} raised {e!r}")
            break
        problems = validate(value)
        if problems:
            out.append(f"sample {value!r} is not a member: {problems}")
        members.append(value)
    for _ in range(outside_draws):
        bad = language.outside(rng)
        if bad is None:
            continue
        if language.contains(bad):
            out.append(f"outside drew a member: {bad!r}")
            continue
        explained = language.explain(bad) or []
        if not explained:
            out.append(f"outside value {bad!r} has no explanation")
        for problem in explained:
            if not _PATH.match(problem.path):
                out.append(f"explanation path {problem.path!r} does not follow the path grammar")
    for value in members[:5]:
        for smaller in language.shrink(value):
            if not language.contains(smaller):
                out.append(f"shrinking {value!r} left the language: {smaller!r}")
    out.extend(_fields_problems(language))
    return out


#: objects no row adaptor should claim
FOREIGN: tuple[Any, ...] = (None, 0, 1.5, "text", b"", [], {}, (), object(), int, str, type("Plain", (), {}))


def foreign_object_problems(adapt: Callable[[Any], Any], *, own_package: str | None = None,
                      foreign: tuple[Any, ...] = FOREIGN) -> list[str]:
    """Every way `adapt` fails to return `None` for objects that are not
    its own, or imports a module outside the standard library, mathema
    and its own package (`own_package`, else the adaptor's top-level
    module) while it runs. A library already imported before the call
    cannot be caught here; run the check in a fresh interpreter for
    that."""
    own = own_package or (getattr(adapt, "__module__", "") or "").split(".")[0]
    allowed = set(sys.stdlib_module_names) | {"mathema", "mathema_language", own}
    before = {name.split(".")[0] for name in sys.modules}
    out = []
    for obj in foreign:
        try:
            answer = adapt(obj)
        except Exception as e:
            out.append(f"{obj!r}: raised {e!r} instead of returning None")
            continue
        if answer is not None:
            out.append(f"{obj!r}: returned {answer!r}, not None")
    imported = {name.split(".")[0] for name in sys.modules} - before - allowed
    if imported:
        out.append(f"imported {sorted(imported)} while checking them")
    return out


__all__ = ["FOREIGN", "foreign_object_problems", "record_adaptor_problems"]
