# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A record language's membership as a z3 formula: the encoding a
solver needs to decide whether every record one schema admits, another
admits too, or whether every record a schema admits meets a condition.

`MembershipEncoding.row(language, names, side)` is the formula over one
z3 variable per field name. On the `older` side it admits at least what
the language's library admits, on the `newer` side at most, so a solver
that finds no value inside the older encoding of one language and
outside the newer encoding of another has proved inclusion, whichever
way a library reads what the encoding cannot pin down: a regular
expression is a search on the older side and a full match on the newer,
and the newer side gets no credit for coercing a value into its type
(pydantic reading `"3"` as `3`). Anything the encoding does not read (a
record inside a list, a custom validator, a JSON Schema keyword the
validator enforces and the adaptor does not read, a decimal with one of
its two digit limits)
raises `Untranslated` naming it; `untranslated(language)` says so before
encoding. A constraint is never dropped.

Each field value is of a single z3 type holding every kind of value a
field can take: absent, null, NaN, the two infinities, a bool, an int,
an exact real and a string. Numbers are exact reals, as mathema's own
z3 rung reads them. z3's strings hold characters up to U+2FFFF; a
record whose text uses a higher one is read as one with each such
character replaced by U+2FFFF, which keeps its length. A regular
expression is read under that replacement on both sides (a class
holding some higher character holds U+2FFFF on the older side, and on
the newer side only when it holds U+2FFFF and every higher character),
so a proof over z3's characters holds over all of Unicode; a constant
that names such a character is not translated.

A Python regular expression, its flags and a mode (`fullmatch`, `match`,
`search`) translate exactly, the newer and older sides one formula, for
the constructs `re` reads as a regular language: literals, classes and
`\\d \\w \\s` as `re` reads them for the running Python's Unicode,
IGNORECASE, ASCII, DOTALL, MULTILINE and VERBOSE, inline and scoped flags,
`^ $ \\A \\Z \\b \\B`, alternation, groups, and greedy and lazy repeats.
Backreferences, lookaround, conditionals, atomic groups, possessive
repeats and an anchor inside an unbounded repeat are `Untranslated`.

`_schema_inclusion` decides inclusion end to end (a value in one and not
the other, built and confirmed by both languages' own validation before
it is reported, and each float bound run again at its neighbouring
doubles); it is how the tests hold the encoding to its two sides. Deciding
such claims, with a route and a record, is mathema's.

The `z3-solver` dependency is the optional `[smt]` extra."""
from __future__ import annotations

import decimal
import math
import re
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import PurePath
from typing import Any

from .schema.model import NO_DEFAULT, Field, RowSchema

#: the ecosystems whose records the encoding reads, and whether a record
#: is a mapping that may leave a key out
_SUPPORTED = {"plain": True, "jsonschema": True, "attribute": False, "pydantic": False,
              "argparse": False}

#: the argparse `type=` converters whose value is read as its text: every
#: string converts, and the encoding holds the text it came from
_TEXT_CONVERTERS = {"Path", "PurePath", "PosixPath", "PurePosixPath", "str"}

#: the JSON Schema keywords `jsonschema` enforces that the adaptor does not
#: read into the neutral model; a keyword it does not enforce (`format`
#: without a format checker, `title`, an OpenAPI `example`) constrains
#: nothing and is ignored
_JSON_SCHEMA_ENFORCED_UNREAD = {
    "not", "allOf", "if", "then", "else", "dependentRequired", "dependentSchemas",
    "dependencies", "propertyNames", "patternProperties", "minProperties", "maxProperties",
    "uniqueItems", "contains", "minContains", "maxContains", "prefixItems",
    "unevaluatedProperties", "unevaluatedItems", "$ref", "$dynamicRef",
}

#: the last character z3's strings hold; a higher one is not passed to
#: z3, which would read it as the text of its escape
_Z3_MAX_CHAR = 0x2FFFF

#: the scalar types the encoding reads
_READ_BASES = {"bool", "int", "float", "decimal", "string", "categorical", "list", "struct", "any"}


class Untranslated(Exception):
    """A construct the encoding does not read, named."""


@dataclass
class _InclusionResult:
    """`verdict` is `proven` (every record `older` admits, `newer`
    admits), `falsified` (with `witness`, a record `older` admits and
    `newer` refuses, confirmed by both validations) or `unknown` (with
    `reason`). `float_line` lists the neighbouring doubles of each float
    bound that were run through both validations, and holds the first
    one `older` admits and `newer` refuses, if any. Between pattern
    languages the witness is a string, and `proven` and `falsified` read
    as each call states."""
    verdict: str
    reason: str = ""
    witness: Any = None
    float_line: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.verdict == "falsified":
            return f"falsified   {self.witness}: {self.reason}"
        return f"{self.verdict}   {self.reason}".rstrip()


def _z3() -> Any:
    """Intent:
        Returns the imported `z3` module.

    Raises:
        ImportError: z3 is not installed (the optional `[smt]` extra).
    """
    try:
        import z3
    except ImportError as e:
        raise ImportError("schema inclusion is decided by z3, which is not installed: "
                          "pip install 'mathema-language[smt]'") from e
    return z3


class MembershipEncoding:
    """One z3 encoding of the field values of two schemas."""

    def __init__(self, z3: Any) -> None:
        self.z3 = z3
        # an item of a list holds the same scalars as a field, and a field
        # may also be absent or hold a list of items
        item = z3.Datatype("Item")
        for tag in ("null", "nan", "pinf", "ninf"):
            item.declare(tag)
        item.declare("b", ("bv", z3.BoolSort()))
        item.declare("i", ("iv", z3.IntSort()))
        item.declare("r", ("rv", z3.RealSort()))
        item.declare("s", ("sv", z3.StringSort()))
        self.I = item.create()
        v = z3.Datatype("Value")
        for tag in ("absent", "null", "nan", "pinf", "ninf"):
            v.declare(tag)
        v.declare("b", ("bv", z3.BoolSort()))
        v.declare("i", ("iv", z3.IntSort()))
        v.declare("r", ("rv", z3.RealSort()))
        v.declare("s", ("sv", z3.StringSort()))
        v.declare("seq", ("items", z3.SeqSort(self.I)))
        self.V = v.create()
        self.vars: dict[str, Any] = {}
        self.extra: list[Any] = []

    def var(self, name: str) -> Any:
        if name not in self.vars:
            self.vars[name] = self.z3.Const(f"f_{len(self.vars)}_{name}", self.V)
        return self.vars[name]

    def const(self, value: Any, D: Any = None) -> Any:
        """A Python value as a z3 Value (or as a list Item, with `D`)."""
        V = D if D is not None else self.V
        if isinstance(value, (list, tuple)) and V is self.V:
            items = [self.z3.Unit(self.const(v, self.I)) for v in value]
            if not items:
                return V.seq(self.z3.Empty(self.z3.SeqSort(self.I)))
            return V.seq(items[0] if len(items) == 1 else self.z3.Concat(*items))
        if value is None:
            return V.null
        if isinstance(value, bool):
            return V.b(self.z3.BoolVal(value))
        if isinstance(value, int):
            return V.i(self.z3.IntVal(value))
        if isinstance(value, float):
            if math.isnan(value):
                return V.nan
            if math.isinf(value):
                return V.pinf if value > 0 else V.ninf
            return V.r(self._real(value))
        if isinstance(value, decimal.Decimal):
            if not value.is_finite():
                raise Untranslated(f"the decimal {value}")
            return V.r(self._real(value))
        if isinstance(value, str):
            if any(ord(ch) > _Z3_MAX_CHAR for ch in value):
                raise Untranslated(f"the text {value!r}, past the characters z3 holds")
            return V.s(self.z3.StringVal(value))
        raise Untranslated(f"the value {value!r}")

    def _real(self, value: Any) -> Any:
        """Intent:
            Returns a finite Python number as an exact z3 real, its numerator over its denominator.
        """
        q = Fraction(value)
        return self.z3.RealVal(f"{q.numerator}/{q.denominator}")

    def _number(self, x: Any, V: Any) -> tuple[Any, Any]:
        """Intent:
            Returns `(is a finite number, its real value)` for the z3 value `x` of datatype `V`,
            an int read as a real.
        """
        return (self.z3.Or(V.is_i(x), V.is_r(x)),
                self.z3.If(V.is_i(x), self.z3.ToReal(V.iv(x)), V.rv(x)))

    def _decimal_digits(self, x: Any, V: Any, scale: int, precision: int | None,
                        side: str, name: str) -> Any:
        """Intent:
            Returns the z3 condition that the number `x` has at most `scale` places after the
            point and, when `precision` is given, at most `precision` digits in all.

            A number has at most `scale` places when its shift by `10**scale` is whole, and then
            at most `precision` digits when that shifted value lies strictly between
            `-10**precision` and `10**precision`. An int always meets the scale, so its arm only
            bounds the digits, in integer arithmetic.

            The two sides state the real arm differently. The newer side, which an inclusion
            negates, states it as a function of `x` alone (the shifted value equals its own
            floor), so negating it leaves the solver nothing to choose. The older side, which an
            inclusion only asserts, builds `x` as a whole number `k` over `10**scale`; the two
            admit the same reals, and the built form is the one z3 decides quickly.
        """
        z3 = self.z3
        shift = 10 ** scale
        bound = 10 ** precision if precision is not None else None
        n = V.iv(x) * shift
        on_int = z3.And(n < bound, n > -bound) if bound is not None else z3.BoolVal(True)
        if side == "older":
            k = z3.Int(f"k_{len(self.extra)}_{name}")
            self.extra.append(k)
            on_real = [x == V.r(z3.ToReal(k) / shift)]
            if bound is not None:
                on_real += [k < bound, k > -bound]
        else:
            scaled = V.rv(x) * shift
            on_real = [V.is_r(x), z3.ToReal(z3.ToInt(scaled)) == scaled]
            if bound is not None:
                on_real += [scaled < bound, scaled > -bound]
        return z3.Or(z3.And(V.is_i(x), on_int), z3.And(*on_real))

    def _bounds(self, f: Field, real: Any) -> list[Any]:
        """Intent:
            Returns one z3 condition on `real` per numeric bound (inclusive or exclusive minimum
            and maximum) field `f` states.

        Raises:
            Untranslated: a bound is a bool or not a number.
        """
        c, out = f.constraints, []
        for bound, op in ((c.min, ">="), (c.max, "<="), (c.exclusive_min, ">"), (c.exclusive_max, "<")):
            if bound is None:
                continue
            if isinstance(bound, bool) or not isinstance(bound, (int, float, decimal.Decimal)):
                raise Untranslated(f"the bound {bound!r} on .{f.name}")
            b = self._real(bound)
            out.append({">=": real >= b, "<=": real <= b, ">": real > b, "<": real < b}[op])
        return out

    def _regex(self, pattern: str, side: str) -> Any:
        """Intent:
            Returns `pattern` as a z3 regular expression over a field's whole text: the strings
            `re.search` finds it in on the older side, those it matches in full on the newer.

        Notes:
            Every string `re.fullmatch` matches, `re.search` finds a match in, so the newer side
            admits no more than the older, whichever of the two a library runs.
        """
        if side == "newer":
            return _pattern_regex(self.z3, pattern, 0, "fullmatch", "newer")
        return _pattern_regex(self.z3, pattern, 0, "search", "older")

    def member(self, f: Field, x: Any, side: str, mapping: bool, D: Any = None,
               path: str | None = None) -> Any:
        """The formula: `x` is a value field `f` admits. `side` is
        `older` (admit at least what the library admits) or `newer`
        (admit at most). With `D`, `x` is a list item of that type.
        `path` is the field's dotted name; a nested record's fields are
        variables of their own under it (`body.sku`), and `x` itself only
        says whether the record is there."""
        z3, c, t = self.z3, f.constraints, f.type
        V = D if D is not None else self.V
        options = []
        if mapping and not f.required and V is self.V:
            options.append(V.is_absent(x))
        if f.nullable:
            options.append(V.is_null(x))
        if t.base not in _READ_BASES:
            raise Untranslated(f"the {t.base} field .{f.name}")
        if t.base == "any":
            if side == "newer":
                raise Untranslated(f"the field .{f.name} of no type the encoding reads")
            options.append(z3.Not(V.is_absent(x)) if V is self.V else z3.BoolVal(True))
            return z3.Or(*options)
        if c.regex is not None and t.base != "string":
            raise Untranslated(f"a pattern on the {t.base} field .{f.name}")
        conds: list[Any] = []
        if t.base == "bool":
            conds.append(V.is_b(x))
        elif t.base == "int":
            conds.append(V.is_i(x))
            n = V.iv(x)
            if t.bits:
                lo, hi = ((-(1 << (t.bits - 1)), (1 << (t.bits - 1)) - 1) if t.signed
                          else (0, (1 << t.bits) - 1))
                conds += [n >= lo, n <= hi]
            conds += self._bounds(f, z3.ToReal(n))
            if c.multiple_of is not None:
                if not isinstance(c.multiple_of, int) or isinstance(c.multiple_of, bool) \
                        or c.multiple_of == 0:
                    raise Untranslated(f"the divisor {c.multiple_of!r} on .{f.name}")
                conds.append(n % c.multiple_of == 0)
        elif t.base in ("float", "decimal"):
            is_num, real = self._number(x, V)
            num = [is_num, *self._bounds(f, real)]
            if c.multiple_of is not None:
                raise Untranslated(f"the divisor on the {t.base} field .{f.name}")
            if t.base == "decimal" and t.scale is not None:
                num.append(self._decimal_digits(x, V, t.scale, t.precision, side, f.name))
            alternatives = [z3.And(*num)]
            if t.base == "float":
                specials = side == "older" or f.nan_allowed
                if specials:
                    c_lo = c.min is not None or c.exclusive_min is not None
                    c_hi = c.max is not None or c.exclusive_max is not None
                    if not c_hi:
                        alternatives.append(V.is_pinf(x))
                    if not c_lo:
                        alternatives.append(V.is_ninf(x))
                    if f.nan_allowed:
                        alternatives.append(V.is_nan(x))
            conds.append(z3.Or(*alternatives))
        elif t.base == "string":
            conds.append(V.is_s(x))
            s = V.sv(x)
            if c.min_len is not None:
                conds.append(z3.Length(s) >= c.min_len)
            if c.max_len is not None:
                conds.append(z3.Length(s) <= c.max_len)
            if c.regex is not None:
                conds.append(z3.InRe(s, self._regex(c.regex, side)))
        elif t.base == "struct":
            if V is not self.V or path is None:
                raise Untranslated(f"the record items of the list field .{f.name}")
            present = [x == V.b(z3.BoolVal(True))]
            for sub in t.fields or ():
                child = f"{path}.{sub.name}"
                present.append(self.member(sub, self.var(child), side, mapping, path=child))
            conds.append(z3.And(*present))
        elif t.base == "list":
            item_t = t.item
            if V is not self.V or item_t is None or item_t.base not in _READ_BASES - {"any", "list"}:
                raise Untranslated(f"the list field .{f.name} of "
                                   f"{item_t.base if item_t else 'unstated'} items")
            conds.append(V.is_seq(x))
            items = V.items(x)
            n = z3.Length(items)
            if c.min_len is not None:
                conds.append(n >= c.min_len)
            if c.max_len is not None:
                conds.append(n <= c.max_len)
            k = z3.Int(f"k_{len(self.extra)}_{f.name}")
            self.extra.append(k)
            item = Field("item", item_t, nullable=f.type.nullable_items)
            conds.append(z3.ForAll([k], z3.Implies(z3.And(k >= 0, k < n),
                                                   self.member(item, items[k], side, False, self.I))))
        elif t.base == "categorical":
            conds.append(z3.Or(*[x == self.const(level, D) for level in (t.levels or ())]) if t.levels
                         else z3.BoolVal(False))
        if c.enum is not None:
            conds.append(z3.Or(*[x == self.const(e, D) for e in c.enum]) if c.enum else z3.BoolVal(False))
        if c.const is not NO_DEFAULT:
            conds.append(x == self.const(c.const, D))
        options.append(z3.And(*conds))
        return z3.Or(*options)

    def present(self, name: str) -> Any:
        """The formula: field `name` is there (not absent, not null)."""
        x = self.var(name)
        return self.z3.And(self.z3.Not(self.V.is_absent(x)), self.z3.Not(self.V.is_null(x)))

    def number(self, name: str) -> tuple[Any, Any]:
        """`(holds a finite number, its exact real value)` for field
        `name`, the terms a relation over a numeric field is written in:
        `x.qty <= 10` is `Implies(is_number, value <= 10)`."""
        return self._number(self.var(name), self.V)

    def string(self, name: str) -> tuple[Any, Any]:
        """`(holds text, the z3 string)` for field `name`."""
        x = self.var(name)
        return self.V.is_s(x), self.V.sv(x)

    def decode(self, model: Any, language: Any, names: list[str]) -> dict[str, Any]:
        """A z3 model of this encoding as the nested value of `language`
        it describes, absent fields left out."""
        values: dict[str, Any] = {}
        for name in names:
            present, value = _value(self, model, self.var(name), _field_at(language, name))
            if present:
                values[name] = value
        return _nest(language, values)

    def text(self, language: Any, x: Any, side: str) -> Any:
        """The formula: the z3 string `x` is a member of a text language
        defined by a regular expression: its `pattern`, under its `flags`
        (none when it states none), read by its `mode` (`fullmatch` when it
        states none, as `L[path]` and `L[path, within "/root"]` are)."""
        pattern = getattr(language, "pattern", None)
        if not isinstance(pattern, (str, re.Pattern)):
            raise Untranslated(f"{getattr(language, 'name', language)!r}, which states no pattern")
        return _pattern(self.z3, pattern, getattr(language, "flags", 0),
                        getattr(language, "mode", "fullmatch"), x, side)

    def language(self, language: Any, names: list[str], side: str) -> Any:
        """The formula: the values of `names` make a member of `language`,
        one of its shapes when it has several (a command line's
        subcommands)."""
        shapes = []
        for b in _branches(language):
            shape = self.row(b.schema, names, side, _SUPPORTED[b.ecosystem.name])
            # the text of a path a converter builds is never empty
            # (`Path("")` is `.`), so neither is the text the encoding holds
            for dest, convert in (getattr(b.ecosystem, "converters", None) or {}).items():
                if dest in names and getattr(convert, "__name__", "") in _TEXT_CONVERTERS - {"str"}:
                    x = self.var(dest)
                    shape = self.z3.And(shape, self.z3.Implies(
                        self.V.is_s(x), self.z3.Length(self.V.sv(x)) >= 1))
            shapes.append(shape)
        formula = shapes[0] if len(shapes) == 1 else self.z3.Or(*shapes)
        # a nested field is there only when the record holding it is
        nested = [self.z3.Implies(self.var(n.rsplit(".", 1)[0]) != self.V.b(self.z3.BoolVal(True)),
                                  self.V.is_absent(self.var(n)))
                  for n in names if "." in n]
        return self.z3.And(formula, *nested) if nested else formula

    def row(self, schema: RowSchema, names: list[str], side: str, mapping: bool) -> Any:
        """The formula: the values of `names` make a record `schema`
        admits."""
        z3, V = self.z3, self.V
        if schema.checks:
            raise Untranslated(f"a check of {schema.name}'s own")
        own = {f.name for f in schema.fields}
        conds = [self.member(f, self.var(f.name), side, mapping, path=f.name) for f in schema.fields]
        for name in names:
            if name in own or "." in name:
                continue
            x = self.var(name)
            if not mapping or schema.column_policy == "exact":
                conds.append(V.is_absent(x))
        return z3.And(*conds) if conds else z3.BoolVal(True)


# -- regular expressions ------------------------------------------------------
#
# A Python pattern, its flags and a mode are a text language: the strings
# `re.<mode>(pattern, s, flags)` finds a match in. The translation builds that
# language as a regular expression over the whole string, in three steps.
#
# 1. Every one-character item (a literal, `.`, a class, a category) is the set
#    of code points it matches, found by running `re` itself over every code
#    point, so `\d`, `\w`, `\s` and IGNORECASE are `re`'s own reading for the
#    running Python. A set is a tuple of disjoint, sorted, inclusive intervals.
# 2. A zero-width assertion (`^`, `$`, `\A`, `\Z`, `\b`, `\B`) holds or fails
#    by the text around its position, so a sub-pattern reads as a list of
#    pieces `(left, body, right)`: it matches a string in `body` wherever the
#    text before the match meets `left` and the text after meets `right`. A
#    context is `(empty, chars, only)`: the text there may be empty (when
#    `empty`), or its adjacent character is in `chars`, and with `only` that
#    character is the whole of it. Contexts are closed under conjunction, and
#    joining two pieces turns the second's left context into a condition on
#    the first's last character (or, when the first matched nothing, into a
#    condition on the text before both), and the first's right context into a
#    condition on the second's first character, likewise.
# 3. The mode reads the pieces against the whole string: fullmatch takes the
#    pieces whose contexts admit empty text on both sides, match puts the
#    right context's text after the body, search puts both around it.
#
# Without backreferences, lookaround, atomic groups and possessive repeats,
# `re` backtracks through every way a pattern can match from a position and
# tries every position, so a match exists exactly when the string is in this
# language.
#
# z3's strings hold code points up to U+2FFFF (H). A string with a higher
# character reads as the same string with each such character replaced by H.
# A set reads, on the older side, as its part up to H, with H added when it
# holds any higher character; on the newer side, as its part up to H, with H
# left out unless the set holds H and every higher character. Each operator
# the translation uses is monotone in its sets, so the older side admits at
# least, and the newer at most, what `re` admits under that reading; the two
# are the same formula when every set agrees with H's membership on all the
# characters above H.

#: the last code point
_MAX_CODE = 0x10FFFF

#: every code point
_FULL: tuple[tuple[int, int], ...] = ((0, _MAX_CODE),)

#: the empty set
_NONE: tuple[tuple[int, int], ...] = ()

#: whether `\B` matches in the empty string, which differs between Pythons
_B_IN_EMPTY = re.search(r"\B", "") is not None


def _cs_union(*sets: Any) -> tuple[tuple[int, int], ...]:
    """Intent:
        Returns the union of interval sets, as sorted disjoint intervals with no two adjacent.
    """
    spans = sorted(span for s in sets for span in s)
    out: list[list[int]] = []
    for lo, hi in spans:
        if out and lo <= out[-1][1] + 1:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return tuple((lo, hi) for lo, hi in out)


def _cs_complement(s: Any) -> tuple[tuple[int, int], ...]:
    """Intent:
        Returns the code points not in `s`.
    """
    out, at = [], 0
    for lo, hi in s:
        if lo > at:
            out.append((at, lo - 1))
        at = hi + 1
    if at <= _MAX_CODE:
        out.append((at, _MAX_CODE))
    return tuple(out)


def _cs_inter(a: Any, b: Any) -> tuple[tuple[int, int], ...]:
    """Intent:
        Returns the code points in both `a` and `b`.
    """
    return _cs_complement(_cs_union(_cs_complement(a), _cs_complement(b)))


def _cs_has(s: Any, code: int) -> bool:
    return any(lo <= code <= hi for lo, hi in s)


def _cs_side(s: Any, side: str) -> tuple[tuple[int, int], ...]:
    """Intent:
        Returns the part of `s` z3 reads on `side`: the code points up to H, with H added on the
        older side when `s` holds a higher one, and H dropped on the newer side unless `s` holds
        H and every higher code point.
    """
    low = _cs_inter(s, ((0, _Z3_MAX_CHAR),))
    high = _cs_inter(s, ((_Z3_MAX_CHAR + 1, _MAX_CODE),))
    if side == "older":
        return _cs_union(low, ((_Z3_MAX_CHAR, _Z3_MAX_CHAR),)) if high else low
    if high == ((_Z3_MAX_CHAR + 1, _MAX_CODE),) and _cs_has(s, _Z3_MAX_CHAR):
        return low
    return _cs_inter(low, ((0, _Z3_MAX_CHAR - 1),))


def _cs_exact(s: Any) -> bool:
    """Intent:
        Returns whether `s` reads the same on both sides: every code point above H is in `s`
        exactly when H is.
    """
    return _cs_side(s, "older") == _cs_side(s, "newer")


def _sre() -> tuple[Any, Any, Any]:
    """Intent:
        Returns the regex parser, compiler and constants modules of the running Python.
    """
    import sys
    if sys.version_info >= (3, 11):
        from re import _compiler, _constants, _parser  # type: ignore[attr-defined]
        return _parser, _compiler, _constants
    import sre_compile
    import sre_constants
    import sre_parse
    return sre_parse, sre_compile, sre_constants


_EVERY_CODE_POINT: list[str] = []


def _every_code_point() -> str:
    """Intent:
        Returns the string of every code point in order, lone surrogates included.
    """
    if not _EVERY_CODE_POINT:
        _EVERY_CODE_POINT.append("".join(map(chr, range(_MAX_CODE + 1))))
    return _EVERY_CODE_POINT[0]


_ITEM_CHARS: dict[tuple[str, int], tuple[tuple[int, int], ...]] = {}


def _item_chars(op: Any, arg: Any, flags: int) -> tuple[tuple[int, int], ...]:
    """Intent:
        Returns the code points one parsed one-character item matches under `flags`: those `re`
        itself matches, found by running the item, repeated, over every code point.

    Notes:
        Such an item reads one character and nothing around it, so the runs of the repeated
        item over the string of every code point are the intervals of its set. A literal
        without IGNORECASE is its own code point.
    """
    parser, compiler, constants = _sre()
    if str(op) == "LITERAL" and not flags & re.IGNORECASE:
        return ((arg, arg),)
    key = (f"{op}:{arg!r}", flags & (re.IGNORECASE | re.ASCII | re.DOTALL | re.UNICODE))
    if key not in _ITEM_CHARS:
        state = (getattr(parser, "State", None) or parser.Pattern)()
        state.flags = flags
        item = parser.SubPattern(state, [(op, arg)])
        repeated = parser.SubPattern(state, [(constants.MAX_REPEAT,
                                              (1, constants.MAXREPEAT, item))])
        compiled = compiler.compile(repeated, flags)
        _ITEM_CHARS[key] = tuple((m.start(), m.end() - 1)
                                 for m in compiled.finditer(_every_code_point()))
    return _ITEM_CHARS[key]


def _class_chars(pattern: str, flags: int = 0) -> tuple[tuple[int, int], ...]:
    """Intent:
        Returns the code points a pattern of one one-character item (`\\d`, `[^a-z]`, `.`)
        matches under `flags`, as `re` reads it.

    Raises:
        Untranslated: the pattern is not one such item.
    """
    parser, _, _ = _sre()
    items = list(parser.parse(pattern, flags))
    if len(items) != 1 or str(items[0][0]) not in ("LITERAL", "NOT_LITERAL", "ANY", "IN", "CATEGORY"):
        raise Untranslated(f"the pattern {pattern!r}, which is not one character item")
    return _item_chars(items[0][0], items[0][1], parser.parse(pattern, flags).state.flags | flags)


# a regular expression, before z3: ("chars", set), ("eps",), ("empty",),
# ("cat", a, b, ...), ("alt", a, b, ...), ("loop", r, lo, hi or None),
# ("inter", a, b)
_EPS = ("eps",)
_EMPTY_RE = ("empty",)
_ANY_STAR = ("loop", ("chars", _FULL), 0, None)
_ANY_PLUS = ("loop", ("chars", _FULL), 1, None)


def _chars_re(s: Any) -> tuple:
    return ("chars", tuple(s)) if s else _EMPTY_RE


def _cat(*parts: tuple) -> tuple:
    flat: list[tuple] = []
    for p in parts:
        if p == _EMPTY_RE:
            return _EMPTY_RE
        if p == _EPS:
            continue
        flat.extend(p[1:] if p[0] == "cat" else [p])
    if not flat:
        return _EPS
    return flat[0] if len(flat) == 1 else ("cat", *flat)


def _alt(*parts: tuple) -> tuple:
    flat: list[tuple] = []
    for p in parts:
        for q in (p[1:] if p[0] == "alt" else [p]):
            if q != _EMPTY_RE and q not in flat:
                flat.append(q)
    if not flat:
        return _EMPTY_RE
    return flat[0] if len(flat) == 1 else ("alt", *flat)


def _inter(a: tuple, b: tuple) -> tuple:
    if _EMPTY_RE in (a, b):
        return _EMPTY_RE
    if b == _ANY_STAR:
        return a
    if a == _ANY_STAR:
        return b
    return ("inter", a, b)


def _loop(r: tuple, lo: int, hi: int | None) -> tuple:
    if hi == 0 or r == _EPS:
        return _EPS
    if r == _EMPTY_RE:
        return _EPS if lo == 0 else _EMPTY_RE
    if lo == hi == 1:
        return r
    return ("loop", r, lo, hi)


def _nullable(r: tuple) -> bool:
    """Intent:
        Returns whether the empty string is in `r`.
    """
    kind = r[0]
    if kind == "eps":
        return True
    if kind in ("chars", "empty"):
        return False
    if kind in ("cat", "inter"):
        return all(_nullable(p) for p in r[1:])
    if kind == "alt":
        return any(_nullable(p) for p in r[1:])
    return r[2] == 0 or _nullable(r[1])


def _nonempty(r: tuple) -> tuple:
    """Intent:
        Returns the non-empty strings of `r`, written without intersecting.

    Notes:
        A non-empty string of a concatenation has a first non-empty part, everything before it
        empty; one of a repeat of a nullable body is some iterations followed by a last
        non-empty one.
    """
    if not _nullable(r):
        return r
    kind = r[0]
    if kind in ("eps", "empty"):
        return _EMPTY_RE
    if kind == "cat":
        parts = r[1:]
        return _alt(*[_cat(_nonempty(parts[i]), *parts[i + 1:]) for i in range(len(parts))])
    if kind == "alt":
        return _alt(*[_nonempty(p) for p in r[1:]])
    if kind == "inter":
        return _inter(_nonempty(r[1]), r[2])
    sub, lo, hi = r[1], r[2], r[3]
    if not _nullable(sub):
        return _loop(sub, 1, hi)
    return _cat(_loop(sub, 0, None if hi is None else hi - 1), _nonempty(sub))


def _edge(r: tuple, chars: Any, at_end: bool) -> tuple:
    """Intent:
        Returns the non-empty strings of `r` whose last character (first, when not `at_end`) is
        in `chars`, written without intersecting where `r` has no intersection of its own.
    """
    kind = r[0]
    if kind in ("eps", "empty"):
        return _EMPTY_RE
    if kind == "chars":
        return _chars_re(_cs_inter(r[1], chars))
    if kind == "alt":
        return _alt(*[_edge(p, chars, at_end) for p in r[1:]])
    if kind == "inter":
        return _inter(_edge(r[1], chars, at_end), r[2])
    if kind == "cat":
        parts = list(r[1:])
        order = range(len(parts) - 1, -1, -1) if at_end else range(len(parts))
        out = []
        for i in order:
            if at_end:
                out.append(_cat(*parts[:i], _edge(parts[i], chars, True)))
            else:
                out.append(_cat(_edge(parts[i], chars, False), *parts[i + 1:]))
            if not _nullable(parts[i]):
                break
        return _alt(*out)
    sub, lo, hi = r[1], r[2], r[3]
    rest = _loop(sub, 0 if _nullable(sub) else max(lo - 1, 0), None if hi is None else hi - 1)
    edge = _edge(sub, chars, at_end)
    return _cat(rest, edge) if at_end else _cat(edge, rest)


def _singles(r: tuple) -> tuple[tuple[int, int], ...]:
    """Intent:
        Returns the code points `c` for which the one-character string `c` is in `r`.
    """
    kind = r[0]
    if kind == "chars":
        return r[1]
    if kind in ("eps", "empty"):
        return _NONE
    if kind == "alt":
        return _cs_union(*[_singles(p) for p in r[1:]])
    if kind == "inter":
        return _cs_inter(_singles(r[1]), _singles(r[2]))
    if kind == "cat":
        parts = r[1:]
        return _cs_union(*[_singles(p) for i, p in enumerate(parts)
                           if all(_nullable(q) for j, q in enumerate(parts) if j != i)])
    sub, lo, hi = r[1], r[2], r[3]
    if (hi is None or hi >= 1) and (lo <= 1 or _nullable(sub)):
        return _singles(sub)
    return _NONE


def _re_sets(r: tuple, out: set) -> set:
    """Intent:
        Returns the character sets `r` names, added to `out`.
    """
    if r[0] == "chars":
        out.add(r[1])
    elif r[0] in ("cat", "alt", "inter"):
        for p in r[1:]:
            _re_sets(p, out)
    elif r[0] == "loop":
        _re_sets(r[1], out)
    return out


# a context: (empty, chars, only); see the section comment
_TRIVIAL = (True, _FULL, False)
_AT_EDGE = (True, _NONE, False)


def _ctx_and(a: tuple, b: tuple) -> tuple:
    """Intent:
        Returns the context that holds exactly where both `a` and `b` hold.
    """
    return (a[0] and b[0], _cs_inter(a[1], b[1]), a[2] or b[2])


def _ctx_possible(c: tuple) -> bool:
    return c[0] or bool(c[1])


def _ctx_text(c: tuple, after: bool) -> tuple:
    """Intent:
        Returns the texts `c` admits on one side of a match: after it when `after`, else before.
    """
    empty, chars, only = c
    if c == _TRIVIAL:
        return _ANY_STAR
    edge = _chars_re(chars) if only else (
        _cat(_chars_re(chars), _ANY_STAR) if after else _cat(_ANY_STAR, _chars_re(chars)))
    return _alt(_EPS, edge) if empty else edge


def _ends_in(body: tuple, c: tuple, at_end: bool) -> tuple[tuple, bool]:
    """Intent:
        Returns the non-empty strings of `body` whose last character (first, when not `at_end`)
        meets context `c`, and whether `c` also requires the text beyond them to be empty.
    """
    empty, chars, only = c
    if only:
        return _chars_re(_cs_inter(_singles(body), chars)), True
    if chars == _FULL:
        return _nonempty(body), False
    return _edge(body, chars, at_end), False


def _join(a: list, b: list) -> list:
    """Intent:
        Returns the pieces of a sub-pattern followed by another, from the pieces of each.
    """
    out = []
    for l1, r1, c1 in a:
        for l2, r2, c2 in b:
            lefts = [(l1, r1)]
            if l2 != _TRIVIAL:
                lefts = []
                if _nullable(r1):
                    lefts.append((_ctx_and(l1, l2), _EPS))
                body, edge = _ends_in(r1, l2, at_end=True)
                lefts.append((_ctx_and(l1, _AT_EDGE) if edge else l1, body))
            rights = [(r2, c2)]
            if c1 != _TRIVIAL:
                rights = []
                if _nullable(r2):
                    rights.append((_EPS, _ctx_and(c1, c2)))
                body, edge = _ends_in(r2, c1, at_end=False)
                rights.append((body, _ctx_and(c2, _AT_EDGE) if edge else c2))
            for left, x in lefts:
                for y, right in rights:
                    out.append((left, _cat(x, y), right))
    return _merge(out)


def _merge(pieces: list) -> list:
    """Intent:
        Returns `pieces` with those of equal contexts joined into one and the impossible ones
        dropped.
    """
    by: dict[tuple, tuple] = {}
    for left, body, right in pieces:
        if body == _EMPTY_RE or not _ctx_possible(left) or not _ctx_possible(right):
            continue
        key = (left, right)
        by[key] = _alt(by[key], body) if key in by else body
    return [(left, body, right) for (left, right), body in by.items()]


def _power(pieces: list, n: int) -> list:
    out = [(_TRIVIAL, _EPS, _TRIVIAL)]
    for _ in range(n):
        out = _join(out, pieces)
    return out


#: the largest repeat count of a sub-pattern with assertions that is written out
_UNROLL = 32


class _Regex:
    """A Python regular expression as pieces, for the constructs `re` reads as a regular
    language; anything else is `Untranslated`, naming the construct."""

    def __init__(self, pattern: Any, flags: int = 0) -> None:
        if isinstance(pattern, re.Pattern):
            pattern, flags = pattern.pattern, pattern.flags | flags
        if not isinstance(pattern, str):
            raise Untranslated(f"the pattern {pattern!r}, a bytes pattern")
        self.pattern = pattern
        parser, _, _ = _sre()
        try:
            re.compile(pattern, flags)
            parsed = parser.parse(pattern, flags)
        except (re.error, ValueError, TypeError) as e:
            raise Untranslated(f"the pattern {pattern!r}, which does not compile ({e})") from e
        self.flags = parsed.state.flags | flags
        if self.flags & re.LOCALE:
            raise Untranslated(f"the pattern {pattern!r}, under the LOCALE flag")
        self.pieces = self._seq(list(parsed), self.flags)

    def _untranslated(self, what: str) -> Untranslated:
        return Untranslated(f"the pattern {self.pattern!r} ({what})")

    def _seq(self, items: Any, flags: int) -> list:
        out = [(_TRIVIAL, _EPS, _TRIVIAL)]
        for op, arg in items:
            out = _join(out, self._item(op, arg, flags))
        return out

    def _item(self, op: Any, arg: Any, flags: int) -> list:
        """Intent:
            Returns one parsed item as pieces.

        Raises:
            Untranslated: the item is a backreference, a lookaround, a conditional, an atomic
                group, a possessive repeat, or an assertion inside an unbounded repeat.
        """
        name = str(op)
        if name in ("LITERAL", "NOT_LITERAL", "ANY", "IN", "CATEGORY"):
            return [(_TRIVIAL, _chars_re(_item_chars(op, arg, flags)), _TRIVIAL)]
        if name in ("MAX_REPEAT", "MIN_REPEAT"):
            lo, hi, sub = arg
            return self._repeat(self._seq(sub, flags), lo, None if hi == sre_maxrepeat() else hi)
        if name == "SUBPATTERN":
            add, remove = arg[1], arg[2]
            return self._seq(arg[-1], (flags | add) & ~remove)
        if name == "BRANCH":
            return _merge([p for b in arg[1] for p in self._seq(b, flags)])
        if name == "AT":
            return self._at(str(arg), flags)
        blocked = {"GROUPREF": "a backreference", "GROUPREF_EXISTS": "a conditional group",
                   "ATOMIC_GROUP": "an atomic group",
                   "POSSESSIVE_REPEAT": "a possessive repeat, which gives nothing back"}
        if name in blocked:
            raise self._untranslated(blocked[name])
        if name in ("ASSERT", "ASSERT_NOT"):
            raise self._untranslated("a lookahead" if arg[0] >= 0 else "a lookbehind")
        raise self._untranslated(name.lower())

    def _repeat(self, body: list, lo: int, hi: int | None) -> list:
        """Intent:
            Returns pieces for `body` repeated `lo` to `hi` times (`None`: unbounded).

        Notes:
            An iteration that matches nothing only adds conditions at one position, so an
            unbounded repeat reads as its non-empty iterations alone.
        """
        if len(body) == 1 and body[0][0] == _TRIVIAL and body[0][2] == _TRIVIAL:
            return [(_TRIVIAL, _loop(body[0][1], lo, hi), _TRIVIAL)]
        if lo > _UNROLL or (hi is not None and hi > _UNROLL):
            raise self._untranslated(f"an assertion inside a repeat of more than {_UNROLL}")
        head = _power(body, lo)
        if hi is not None:
            return _join(head, _power(_merge([*body, (_TRIVIAL, _EPS, _TRIVIAL)]), hi - lo))
        steps = _merge([(left, _nonempty(r), right) for left, r, right in body])
        if any(left != _TRIVIAL or right != _TRIVIAL for left, _, right in steps):
            raise self._untranslated("an anchor or word boundary inside an unbounded repeat")
        return _join(head, [(_TRIVIAL, _loop(steps[0][1], 0, None) if steps else _EPS, _TRIVIAL)])

    def _at(self, name: str, flags: int) -> list:
        """Intent:
            Returns the pieces of a zero-width assertion, read as `re` reads it under `flags`.
        """
        newline = ((10, 10),)
        multiline = bool(flags & re.MULTILINE)
        if name == "AT_BEGINNING" and multiline:
            return [((True, newline, False), _EPS, _TRIVIAL)]
        if name in ("AT_BEGINNING", "AT_BEGINNING_STRING"):
            return [(_AT_EDGE, _EPS, _TRIVIAL)]
        if name == "AT_END":
            return [(_TRIVIAL, _EPS, (True, newline, not multiline))]
        if name == "AT_END_STRING":
            return [(_TRIVIAL, _EPS, _AT_EDGE)]
        if name in ("AT_BOUNDARY", "AT_NON_BOUNDARY"):
            parser, _, _ = _sre()
            word_item = list(parser.parse(r"\w", flags & re.ASCII))[0]
            word = _item_chars(*word_item, flags & ~re.IGNORECASE)
            other = _cs_complement(word)
            if name == "AT_BOUNDARY":
                return [((False, word, False), _EPS, (True, other, False)),
                        ((True, other, False), _EPS, (False, word, False))]
            pieces = [((False, word, False), _EPS, (False, word, False)),
                      ((False, other, False), _EPS, (True, other, False)),
                      (_AT_EDGE, _EPS, (False, other, False))]
            if _B_IN_EMPTY:
                pieces.append((_AT_EDGE, _EPS, _AT_EDGE))
            return pieces
        raise self._untranslated(name.lower())

    def language(self, mode: str) -> tuple:
        """Intent:
            Returns the whole strings `re.<mode>` finds a match in.
        """
        if mode not in ("fullmatch", "match", "search"):
            raise ValueError(f"a mode is fullmatch, match or search, not {mode!r}")
        parts = []
        for left, body, right in self.pieces:
            if mode != "search" and not left[0]:
                continue
            if mode == "fullmatch":
                if right[0]:
                    parts.append(body)
                continue
            before = _EPS if mode == "match" else _ctx_text(left, after=False)
            parts.append(_cat(before, body, _ctx_text(right, after=True)))
        return _alt(*parts)

    def sets(self) -> set:
        """Intent:
            Returns every character set the pieces name, in bodies and contexts.
        """
        out: set = set()
        for left, body, right in self.pieces:
            _re_sets(body, out)
            out.update({left[1], right[1]})
        return out


_REGEX_CACHE: dict[tuple[Any, int], _Regex] = {}


def _translated(pattern: Any, flags: int) -> _Regex:
    """Intent:
        Returns the pieces of `pattern` under `flags`, translated once per pattern.

    Raises:
        Untranslated: the pattern holds a construct the translation does not read.
    """
    key = (pattern, int(flags))
    if key not in _REGEX_CACHE:
        _REGEX_CACHE[key] = _Regex(pattern, int(flags))
    return _REGEX_CACHE[key]


def _z3_text(z3: Any, text: str) -> Any:
    """Intent:
        Returns `text` as a z3 string, every character written as its code point so that none
        is read as part of an escape.
    """
    return z3.StringVal("".join("\\u{%x}" % ord(c) for c in text))


def _text_of(model: Any, x: Any) -> str:
    """Intent:
        Returns the Python string a z3 model gives the string `x`, read one code point at a
        time.
    """
    import z3
    n = model.eval(z3.Length(x), model_completion=True).as_long()
    return "".join(chr(model.eval(z3.StrToCode(z3.SubString(x, i, 1)), model_completion=True)
                       .as_long()) for i in range(n))


def _to_z3(z3: Any, r: tuple, side: str, alphabet: Any = None) -> Any:
    """Intent:
        Returns `r` as a z3 regular expression, each character set read on `side`, and, given
        an `_Alphabet`, written over its representatives.
    """
    R = z3.ReSort(z3.StringSort())
    memo: dict[int, Any] = {}

    def char(code: int) -> Any:
        return _z3_text(z3, chr(code))

    def go(node: tuple) -> Any:
        if id(node) in memo:
            return memo[id(node)]
        kind = node[0]
        if kind == "eps":
            out = z3.Re(z3.StringVal(""))
        elif kind == "empty":
            out = z3.Empty(R)
        elif kind == "chars":
            s = _cs_side(node[1], side)
            if alphabet is not None:
                s = alphabet.squeeze(s)
            if not s:
                out = z3.Empty(R)
            elif s == ((0, _Z3_MAX_CHAR),):
                out = z3.AllChar(R)
            else:
                ranges = [z3.Re(char(lo)) if lo == hi else z3.Range(char(lo), char(hi))
                          for lo, hi in s]
                out = ranges[0] if len(ranges) == 1 else z3.Union(*ranges)
        elif kind == "cat":
            out = z3.Concat(*[go(p) for p in node[1:]])
        elif kind == "alt":
            out = z3.Union(*[go(p) for p in node[1:]])
        elif kind == "inter":
            out = z3.Intersect(go(node[1]), go(node[2]))
        else:
            sub, lo, hi = go(node[1]), node[2], node[3]
            if hi is None:
                out = z3.Star(sub) if lo == 0 else (
                    z3.Plus(sub) if lo == 1 else z3.Concat(z3.Loop(sub, lo, lo), z3.Star(sub)))
            elif lo == 0 and hi == 1:
                out = z3.Option(sub)
            else:
                out = z3.Loop(sub, lo, hi)
        memo[id(node)] = out
        return out

    return go(r)


class _Alphabet:
    """The atoms of the character sets some regular expressions name: the classes of z3's
    characters (up to U+2FFFF) that no set tells apart, each written as its least character.

    A language built from those sets by concatenation, union, repetition and intersection holds
    a string exactly when it holds the string with each character replaced by its atom's
    representative, so a question about membership in such languages alone has the same answer
    over the representatives, and a string over them is a witness as it stands."""

    def __init__(self, sets: Any) -> None:
        import bisect
        self._bisect = bisect
        sets = list(sets)
        cuts = {0, _Z3_MAX_CHAR + 1}
        for s in sets:
            for lo, hi in s:
                cuts.update(c for c in (lo, hi + 1) if c <= _Z3_MAX_CHAR + 1)
        self.starts = sorted(cuts)[:-1]
        starts_of = [[lo for lo, _ in s] for s in sets]
        reps: dict[tuple, int] = {}
        self.rep_at: list[int] = []
        for start in self.starts:
            key = tuple(self._has(s, starts, start) for s, starts in zip(sets, starts_of))
            self.rep_at.append(reps.setdefault(key, start))
        self.reps = sorted(set(self.rep_at))

    def _has(self, s: Any, starts: list[int], code: int) -> bool:
        i = self._bisect.bisect_right(starts, code) - 1
        return i >= 0 and s[i][1] >= code

    def rep(self, code: int) -> int:
        """Intent:
            Returns the representative of the atom holding the character `code` (up to H).
        """
        return self.rep_at[self._bisect.bisect_right(self.starts, code) - 1]

    def squeeze(self, s: Any) -> tuple[tuple[int, int], ...]:
        """Intent:
            Returns the representatives `s` holds, `s` being a union of atoms.
        """
        starts = [lo for lo, _ in s]
        return _cs_union(*[((r, r),) for r in self.reps if self._has(s, starts, r)])

    def text(self, text: str) -> str:
        """Intent:
            Returns `text` with each character replaced by its atom's representative, a
            character past U+2FFFF read as U+2FFFF.
        """
        return "".join(chr(self.rep(min(ord(c), _Z3_MAX_CHAR))) for c in text)


def _squeezed(z3: Any, wanted: Any) -> list[Any]:
    """Intent:
        Returns, for each `(language, side)` of pattern languages, its z3 regular expression
        written over the representatives of the atoms of every set all of them name.

    Raises:
        Untranslated: a pattern holds a construct the translation does not read.
    """
    trees = [(_translated(lang.pattern, lang.flags).language(lang.mode), side)
             for lang, side in wanted]
    sets = {_cs_side(s, side) for tree, side in trees for s in _re_sets(tree, set())}
    alphabet = _Alphabet(sets)
    return [_to_z3(z3, tree, side, alphabet) for tree, side in trees]


def _decides(pattern: Any, flags: int, mode: str, side: str, text: str) -> bool:
    """Intent:
        Returns whether z3 finds the string `text` in the translation of
        `re.<mode>(pattern, ., flags)` on `side`, asked over the atoms of the pattern's own
        sets, a character past U+2FFFF read as U+2FFFF.

    Raises:
        Untranslated: the pattern holds a construct the translation does not read.
        RuntimeError: z3 did not decide it.
    """
    z3 = _z3()
    tree = _translated(pattern, flags).language(mode)
    alphabet = _Alphabet({_cs_side(s, side) for s in _re_sets(tree, set())})
    solver = z3.Solver()
    solver.add(z3.InRe(_z3_text(z3, alphabet.text(text)), _to_z3(z3, tree, side, alphabet)))
    answer = solver.check()
    if answer == z3.unknown:
        raise RuntimeError(f"z3 did not decide {text!r} in {pattern!r} ({solver.reason_unknown()})")
    return answer == z3.sat


def _pattern_regex(z3: Any, pattern: Any, flags: int, mode: str, side: str) -> Any:
    """Intent:
        Returns, as a z3 regular expression, the strings `re.<mode>(pattern, s, flags)` finds a
        match in: at least those on the older side, at most those on the newer.

    Raises:
        Untranslated: the pattern holds a construct the translation does not read.
    """
    return _to_z3(z3, _translated(pattern, flags).language(mode), side)


def _pattern(z3: Any, pattern: Any, flags: int, mode: str, x: Any, side: str) -> Any:
    """Intent:
        Returns the formula: `re.<mode>(pattern, x, flags)` finds a match in the z3 string `x`,
        read at least as `re` reads it on the older side and at most on the newer, the same
        formula wherever `_exact(pattern, flags)`.

    Raises:
        Untranslated: the pattern holds a construct the translation does not read, named.
    """
    return z3.InRe(x, _pattern_regex(z3, pattern, flags, mode, side))


def _exact(pattern: Any, flags: int = 0) -> bool:
    """Intent:
        Returns whether the two sides of the translation of `pattern` coincide: whether every
        character set it names treats the code points above U+2FFFF as it treats U+2FFFF.

    Raises:
        Untranslated: the pattern holds a construct the translation does not read, named.
    """
    return all(_cs_exact(s) for s in _translated(pattern, flags).sets())


@dataclass(frozen=True)
class _PatternLanguage:
    """The text language of a pattern under `flags` and a `mode`: the strings
    `re.<mode>(pattern, s, flags)` finds a match in."""
    pattern: str
    flags: int = 0
    mode: str = "fullmatch"

    @property
    def name(self) -> str:
        return f"re.{self.mode}({self.pattern!r}, flags={self.flags})"

    def contains(self, value: Any) -> bool:
        return isinstance(value, str) and getattr(re, self.mode)(self.pattern, value,
                                                                 self.flags) is not None


def sre_maxrepeat() -> int:
    """The repeat count the regex parser uses for an unbounded repeat."""
    import sys
    if sys.version_info >= (3, 11):
        from re import _constants  # type: ignore[attr-defined]
        return int(_constants.MAXREPEAT)
    import sre_constants
    return int(sre_constants.MAXREPEAT)


def _branches(language: Any) -> list[Any]:
    """Intent:
        Returns the record languages a language is the union of: its shapes, or itself.
    """
    return list(getattr(language, "branches", None) or [language])


def _fields(language: Any) -> dict[str, Field]:
    """Intent:
        Returns every top-level field of a language's shapes by name, the first shape naming a
        field deciding which one.
    """
    out: dict[str, Field] = {}
    for branch in _branches(language):
        for f in branch.schema.fields:
            out.setdefault(f.name, f)
    return out


def field_names(language: Any) -> list[str]:
    """Every field name of a language once, a nested record's fields by
    their dotted name after the record's own: the variables an encoding
    of the language uses, and the union two languages share when one is
    checked against the other."""
    out: list[str] = []

    def walk(fields: Any, prefix: str) -> None:
        for f in fields or ():
            name = prefix + f.name
            out.append(name)
            if f.type.base == "struct":
                walk(f.type.fields, name + ".")
    for branch in _branches(language):
        walk(branch.schema.fields, "")
    return list(dict.fromkeys(out))


def _field_at(language: Any, name: str) -> Field | None:
    """Intent:
        Returns the field a dotted name names in any of the language's shapes, or None.
    """
    fields: Any = [f for b in _branches(language) for f in b.schema.fields]
    found = None
    for part in name.split("."):
        found = next((f for f in fields if f.name == part), None)
        if found is None:
            return None
        fields = found.type.fields or ()
    return found


def _nest(language: Any, values: dict[str, Any]) -> dict[str, Any]:
    """Intent:
        Returns values keyed by dotted name as the nested record they describe: a record that is
        there holds its fields, one that is null is None.
    """
    out: dict[str, Any] = {}
    for name in sorted(values, key=lambda n: n.count(".")):
        f = _field_at(language, name)
        value = {} if f is not None and f.type.base == "struct" and values[name] is True \
            else values[name]
        *parents, last = name.split(".")
        holder: Any = out
        for part in parents:
            holder = holder.get(part) if isinstance(holder, dict) else None
        if isinstance(holder, dict):
            holder[last] = value
    return out


def untranslated(language: Any) -> str | None:
    """Why a language's records cannot be encoded, or None."""
    if language is not None and getattr(language, "branches", None):
        for branch in language.branches:
            why = untranslated(branch)
            if why:
                return why
        return None
    ecosystem = getattr(language, "ecosystem", None)
    schema = getattr(language, "schema", None)
    if language is None or ecosystem is None or schema is None:
        return f"{getattr(language, 'name', language)!r} is not a record language"
    if ecosystem.name not in _SUPPORTED:
        return f"{language.name}: {ecosystem.name} records are not read by the encoding yet"
    if ecosystem.name == "pydantic":
        decorators = getattr(ecosystem.model, "__pydantic_decorators__", None)
        if decorators is not None and (decorators.field_validators or decorators.model_validators):
            return f"{language.name}: a custom validator"
        unread = _unread_pydantic(ecosystem.model, schema)
        if unread:
            return f"{language.name}: {unread}"
    if ecosystem.name == "argparse":
        for dest, convert in (getattr(ecosystem, "converters", None) or {}).items():
            if dest in {f.name for f in schema.fields} \
                    and getattr(convert, "__name__", "") not in _TEXT_CONVERTERS:
                return f"{language.name}: the type {getattr(convert, '__name__', convert)!r} of {dest}"
    if ecosystem.name == "jsonschema":
        keywords = _unread_keywords(ecosystem.schema)
        if keywords:
            return f"{language.name}: the JSON Schema keyword {sorted(keywords)[0]!r}"
    return None


#: the pydantic field metadata the adaptor reads into the neutral model,
#: by marker type; settings that only loosen or only tighten coercion are
#: read as no constraint, which the encoding's sides already allow for
_PYDANTIC_MARKERS = {"Gt", "Ge", "Lt", "Le", "MinLen", "MaxLen", "MultipleOf", "Strict"}
_PYDANTIC_SETTINGS = {"pattern", "max_digits", "decimal_places", "allow_inf_nan", "strict"}


def _unread_pydantic(model: Any, schema: RowSchema) -> str | None:
    """Intent:
        Names the first piece of a pydantic model's field metadata the neutral model does not
        carry, or returns None.
    """
    fields = {f.name: f for f in schema.fields}
    for name, info in getattr(model, "model_fields", {}).items():
        for marker in getattr(info, "metadata", ()) or ():
            kind = type(marker).__name__
            if kind == "_PydanticGeneralMetadata":
                given = {k for k, v in vars(marker).items() if v is not None}
                odd = given - _PYDANTIC_SETTINGS
                if odd:
                    return f"the setting {sorted(odd)[0]!r} on .{name}"
                if given & {"max_digits", "decimal_places"}:
                    t = fields[name].type if name in fields else None
                    if t is None or t.precision is None or t.scale is None:
                        return f"decimal digits on .{name} the neutral model does not carry"
            elif kind not in _PYDANTIC_MARKERS:
                return f"the {kind} constraint on .{name}"
    return None


def _nullable_pair(options: Any) -> bool:
    """Intent:
        Whether an `anyOf` or `oneOf` list is one type and `null`, the one shape of either the
        adaptor reads (as a nullable field).
    """
    return isinstance(options, list) and len(options) == 2 \
        and sum(1 for o in options if isinstance(o, dict) and o.get("type") == "null") == 1


def _unread_keywords(schema: Any, nested: bool = False) -> set[str]:
    """Intent:
        Returns the keywords of a JSON Schema, and of its properties, that the validator enforces
        and the neutral model does not carry.

    Notes:
        `additionalProperties` is carried at the top only, so `nested` marks a property's schema.
    """
    out: set[str] = set()
    if not isinstance(schema, dict):
        return out
    out |= set(schema) & _JSON_SCHEMA_ENFORCED_UNREAD
    for key in ("anyOf", "oneOf"):
        options = schema.get(key)
        if options is not None and not _nullable_pair(options):
            out.add(key)
    if nested and "additionalProperties" in schema and schema["additionalProperties"] is not True:
        out.add("additionalProperties (on a nested object)")
    for prop in (schema.get("properties") or {}).values():
        out |= _unread_keywords(prop, nested=True)
    return out


def _value(enc: MembershipEncoding, model: Any, x: Any, f: Field | None) -> tuple[bool, Any]:
    """Intent:
        Returns `(present, value)` for the z3 variable `x` of one field in z3's model, a list as
        the Python list of its items.
    """
    z3, V = enc.z3, enc.V
    v = model.eval(x, model_completion=True)
    if z3.is_true(model.eval(V.is_absent(v))):
        return False, None
    if z3.is_true(model.eval(V.is_seq(v))):
        items = model.eval(V.items(v), model_completion=True)
        n = model.eval(z3.Length(items)).as_long()
        item_f = Field("item", f.type.item) if f is not None and f.type.item is not None else None
        return True, [_scalar(enc, model, model.eval(items[k], model_completion=True), enc.I, item_f)
                      for k in range(n)]
    return True, _scalar(enc, model, v, V, f)


def _scalar(enc: MembershipEncoding, model: Any, v: Any, D: Any, f: Field | None) -> Any:
    """Intent:
        Returns the Python value of one z3 scalar in the model, a number as the field's own type
        (float or decimal) and text with z3's escapes undone.
    """
    z3 = enc.z3
    if z3.is_true(model.eval(D.is_null(v))):
        return None
    for tag, val in (("nan", math.nan), ("pinf", math.inf), ("ninf", -math.inf)):
        if z3.is_true(model.eval(getattr(D, f"is_{tag}")(v))):
            return val
    if z3.is_true(model.eval(D.is_b(v))):
        return z3.is_true(model.eval(D.bv(v)))
    if z3.is_true(model.eval(D.is_i(v))):
        n = model.eval(D.iv(v)).as_long()
        if f is not None and f.type.base == "float":
            return float(n)
        if f is not None and f.type.base == "decimal":
            return decimal.Decimal(n)
        return n
    if z3.is_true(model.eval(D.is_r(v))):
        r = model.eval(D.rv(v))
        q = Fraction(r.numerator_as_long(), r.denominator_as_long())
        if f is not None and f.type.base == "decimal":
            return decimal.Decimal(q.numerator) / decimal.Decimal(q.denominator)
        return float(q)
    text = model.eval(D.sv(v)).as_string()
    return re.sub(r"\\u\{([0-9a-fA-F]+)\}", lambda m: chr(int(m.group(1), 16)), text)


def new_encoding(z3: Any = None) -> MembershipEncoding:
    """A fresh encoding context, one per claim: every language encoded in
    it shares one z3 variable per field name."""
    return MembershipEncoding(z3 if z3 is not None else _z3())


def build(language: Any, values: dict[str, Any]) -> Any:
    """The record `language` builds from `values` (nested, or by dotted
    name): the first of its shapes whose record it admits, else the first
    record a shape builds, else None when no shape's class builds one.
    A caller confirms a candidate with `language.contains(build(...))`."""
    built = []
    for branch in _branches(language):
        try:
            row = branch.ecosystem.build_row(branch.schema, _nest(branch, values))
        except Exception:
            continue
        if branch.contains(row):
            return row
        built.append(row)
    return built[0] if built else None


def _admits(language: Any, values: dict[str, Any]) -> bool:
    """Intent:
        Whether the record built from `values` is a member, the language's own validation
        deciding; a record its class refuses to build is not.

    Notes:
        A language of several shapes admits the record when one of them does.
    """
    if getattr(language, "branches", None):
        return any(_admits(branch, values) for branch in language.branches)
    names = {f.name for f in language.schema.fields}
    mapping = _SUPPORTED.get(language.ecosystem.name, True)
    values = _nest(language, values)
    given = values if mapping or language.schema.column_policy == "exact" \
        else {k: v for k, v in values.items() if k in names}
    try:
        row = language.ecosystem.build_row(language.schema, dict(given))
    except Exception:
        return False
    return bool(language.contains(row))


def _float_line(older: Any, newer: Any, base: dict[str, Any] | None) -> tuple[list[str], dict[str, Any] | None]:
    """Intent:
        Runs each float bound and its neighbouring doubles through both validations on the member
        `base` of `older`, returning the points tried and the first record `older` admits and
        `newer` refuses, if any.
    """
    tried: list[str] = []
    if base is None:
        return tried, None
    fields = _fields(older)
    for f in [*fields.values(), *_fields(newer).values()]:
        if f.type.base != "float" or f.name not in fields:
            continue
        c = f.constraints
        for bound in (c.min, c.max, c.exclusive_min, c.exclusive_max):
            if not isinstance(bound, (int, float)) or isinstance(bound, bool):
                continue
            b = float(bound)
            for point in (math.nextafter(b, -math.inf), b, math.nextafter(b, math.inf)):
                values = {**base, f.name: point}
                tried.append(f".{f.name} = {point!r}")
                if _admits(older, values) and not _admits(newer, values):
                    return tried, values
    return tried, None


def _schema_inclusion(older: Any, newer: Any, *, timeout_ms: int = 5000) -> _InclusionResult:
    """Intent:
        Decides whether `newer` admits every record `older` admits: `proven`, `falsified` with a
        record both validations confirm `older` admits and `newer` refuses, or `unknown`.

    Notes:
        `older` and `newer` are record languages, or anything `L[...]` resolves (a model class,
        a JSON Schema dict). A proof is followed by a run at each float bound's neighbouring
        doubles, which can still falsify it.
    """
    z3 = _z3()
    from .schema.adaptors import adapt_row
    older, newer = (x if hasattr(x, "ecosystem") or getattr(x, "branches", None) else adapt_row(x)
                    for x in (older, newer))
    for language in (older, newer):
        why = untranslated(language)
        if why:
            return _InclusionResult("unknown", f"not translated: {why}")
    enc = MembershipEncoding(z3)
    names = list(dict.fromkeys([*field_names(older), *field_names(newer)]))
    try:
        m_older = enc.language(older, names, "older")
        m_newer = enc.language(newer, names, "newer")
    except Untranslated as e:
        return _InclusionResult("unknown", f"not translated: {e}")
    solver = z3.Solver()
    solver.set("timeout", timeout_ms)
    solver.add(m_older, z3.Not(m_newer))
    # a witness reads best with the keys `older` does not declare left out,
    # so those are tried absent first and allowed only if they must be
    own = set(field_names(older))
    undeclared = [enc.V.is_absent(enc.var(n)) for n in names if n not in own]
    answer = solver.check(*undeclared) if undeclared else solver.check()
    if answer != z3.sat and undeclared:
        answer = solver.check()
    if answer == z3.unknown:
        return _InclusionResult("unknown", f"z3 did not decide it ({solver.reason_unknown()})")
    if answer == z3.unsat:
        base = _a_member(older)
        tried, edge = _float_line(older, newer, base)
        if edge is not None:
            return _InclusionResult("falsified", "at a float bound's neighbouring double, "
                                   f"{older.name} admits it and {newer.name} refuses it",
                                   edge, tried)
        return _InclusionResult("proven", f"every record {older.name} admits, {newer.name} admits",
                               float_line=tried)
    model = solver.model()
    values: dict[str, Any] = {}
    for name in names:
        f = _field_at(older, name) or _field_at(newer, name)
        present, value = _value(enc, model, enc.var(name), f)
        if present:
            values[name] = value
    if _admits(older, values) and not _admits(newer, values):
        return _InclusionResult("falsified", f"{older.name} admits it and {newer.name} refuses it",
                               _nest(older, values))
    return _InclusionResult("unknown", f"z3 offered {values!r}, which the validations do not "
                           f"confirm ({older.name} must admit it and {newer.name} refuse it); "
                           "this is a gap in the encoding")


def _text_language(spec: Any) -> _PatternLanguage:
    """Intent:
        Returns the pattern language `spec` names: a `_PatternLanguage`, a
        `(pattern, flags, mode)` triple, or a pattern alone, read in full.
    """
    if isinstance(spec, _PatternLanguage):
        return spec
    if isinstance(spec, tuple):
        return _PatternLanguage(*spec)
    return _PatternLanguage(spec)


def _solve_text(wanted: Any, inside: list[bool], timeout_ms: int) -> tuple[str, Any]:
    """Intent:
        Returns z3's answer on a string `x` in each `(language, side)` of `wanted` whose `inside`
        flag is set and outside each other one: `unsat`, `sat` with the string a model gives
        `x`, or `unknown` with z3's reason.

    Raises:
        Untranslated: a pattern holds a construct the translation does not read.
    """
    z3 = _z3()
    x = z3.String("x")
    solver = z3.Solver()
    solver.set("timeout", timeout_ms)
    for regex, keep in zip(_squeezed(z3, wanted), inside):
        solver.add(z3.InRe(x, regex) if keep else z3.Not(z3.InRe(x, regex)))
    answer = solver.check()
    if answer == z3.unsat:
        return "unsat", None
    if answer == z3.sat:
        return "sat", _text_of(solver.model(), x)
    return "unknown", solver.reason_unknown()


def _text_inclusion(a: Any, b: Any, *, timeout_ms: int = 5000) -> _InclusionResult:
    """Intent:
        Decides whether every string pattern language `a` holds, `b` holds: `proven`,
        `falsified` with a string `re` confirms is in `a` and not in `b`, or `unknown` with the
        reason.
    """
    a, b = _text_language(a), _text_language(b)
    try:
        answer, found = _solve_text([(a, "older"), (b, "newer")], [True, False], timeout_ms)
    except Untranslated as e:
        return _InclusionResult("unknown", f"not translated: {e}")
    if answer == "unsat":
        return _InclusionResult("proven", f"every string {a.name} holds, {b.name} holds")
    if answer == "unknown":
        return _InclusionResult("unknown", f"z3 did not decide it ({found})")
    if a.contains(found) and not b.contains(found):
        return _InclusionResult("falsified", f"{a.name} holds it and {b.name} does not", found)
    return _InclusionResult("unknown", f"z3 offered {found!r}, which re does not confirm "
                            f"({a.name} must hold it and {b.name} not)")


def _text_emptiness(a: Any, *, timeout_ms: int = 5000) -> _InclusionResult:
    """Intent:
        Decides whether pattern language `a` holds no string: `proven`, `falsified` with a
        string `re` confirms it holds, or `unknown` with the reason.
    """
    a = _text_language(a)
    try:
        answer, found = _solve_text([(a, "older")], [True], timeout_ms)
    except Untranslated as e:
        return _InclusionResult("unknown", f"not translated: {e}")
    if answer == "unsat":
        return _InclusionResult("proven", f"{a.name} holds no string")
    if answer == "unknown":
        return _InclusionResult("unknown", f"z3 did not decide it ({found})")
    if a.contains(found):
        return _InclusionResult("falsified", f"{a.name} holds it", found)
    return _InclusionResult("unknown", f"z3 offered {found!r}, which re does not confirm")


def _text_disjointness(a: Any, b: Any, *, timeout_ms: int = 5000) -> _InclusionResult:
    """Intent:
        Decides whether pattern languages `a` and `b` share no string: `proven`, `falsified`
        with a string `re` confirms both hold, or `unknown` with the reason.
    """
    a, b = _text_language(a), _text_language(b)
    try:
        answer, found = _solve_text([(a, "older"), (b, "older")], [True, True], timeout_ms)
    except Untranslated as e:
        return _InclusionResult("unknown", f"not translated: {e}")
    if answer == "unsat":
        return _InclusionResult("proven", f"no string is held by both {a.name} and {b.name}")
    if answer == "unknown":
        return _InclusionResult("unknown", f"z3 did not decide it ({found})")
    if a.contains(found) and b.contains(found):
        return _InclusionResult("falsified", f"both {a.name} and {b.name} hold it", found)
    return _InclusionResult("unknown", f"z3 offered {found!r}, which re does not confirm")


def _text_equivalence(a: Any, b: Any, *, timeout_ms: int = 5000) -> _InclusionResult:
    """Intent:
        Decides whether pattern languages `a` and `b` hold the same strings: `proven` when each
        includes the other, `falsified` with a string `re` confirms one holds and the other does
        not, or `unknown` with the reason.
    """
    ab = _text_inclusion(a, b, timeout_ms=timeout_ms)
    if ab.verdict == "falsified":
        return ab
    ba = _text_inclusion(b, a, timeout_ms=timeout_ms)
    if ba.verdict == "falsified":
        return ba
    if ab.verdict == ba.verdict == "proven":
        a, b = _text_language(a), _text_language(b)
        return _InclusionResult("proven", f"{a.name} and {b.name} hold the same strings")
    return ab if ab.verdict == "unknown" else ba


def _field_in(language: Any, name: str, text_language: Any, *,
              timeout_ms: int = 5000) -> _InclusionResult:
    """Intent:
        Decides whether every member of `language` whose field `name` holds text has that text in
        `text_language`: `proven`, `falsified` with a confirmed record, or `unknown`.
    """
    z3 = _z3()
    why = untranslated(language)
    if why:
        return _InclusionResult("unknown", f"not translated: {why}")
    enc = MembershipEncoding(z3)
    names = field_names(language)
    try:
        member = enc.language(language, names, "older")
        x = enc.var(name)
        inside = enc.text(text_language, enc.V.sv(x), "newer")
    except Untranslated as e:
        return _InclusionResult("unknown", f"not translated: {e}")
    solver = z3.Solver()
    solver.set("timeout", timeout_ms)
    solver.add(member, enc.V.is_s(x), z3.Not(inside))
    answer = solver.check()
    if answer == z3.unknown:
        return _InclusionResult("unknown", f"z3 did not decide it ({solver.reason_unknown()})")
    if answer == z3.unsat:
        return _InclusionResult("proven", f"every {name} {language.name} admits is in "
                                f"L[{text_language.name}]")
    model = solver.model()
    values = {}
    for n in names:
        present, value = _value(enc, model, enc.var(n), _field_at(language, n))
        if present:
            values[n] = value
    received = _received(language, values, name)
    if _admits(language, values) and received is not None and not text_language.contains(received):
        return _InclusionResult("falsified", f"{name} is not in L[{text_language.name}]",
                               _nest(language, values))
    return _InclusionResult("unknown", f"z3 offered {values!r}, which does not confirm")


def _received(language: Any, values: dict[str, Any], name: str) -> Any:
    """Intent:
        Returns field `name` of the record the first admitting shape builds from `values`, as a
        program receives it (a path as its text), or None when no shape admits it.
    """
    for branch in _branches(language):
        try:
            row = branch.ecosystem.build_row(branch.schema, _nest(branch, values))
        except Exception:
            continue
        if not branch.contains(row):
            continue
        value: Any = row
        for part in name.split("."):
            value = value.get(part) if isinstance(value, dict) else getattr(value, part, None)
        return str(value) if isinstance(value, PurePath) else value
    return None


def _a_member(language: Any) -> dict[str, Any] | None:
    """Intent:
        Returns the top-level field values of one member the language samples with a fixed seed,
        or None when it cannot sample one.
    """
    import random
    try:
        row = language.sample(random.Random(0))
    except Exception:
        return None
    out = {}
    for f in _fields(language).values():
        if isinstance(row, dict):
            if f.name in row:
                out[f.name] = row[f.name]
        elif hasattr(row, f.name):
            out[f.name] = getattr(row, f.name)
    return out


__all__ = ["MembershipEncoding", "Untranslated", "build", "field_names", "new_encoding",
           "untranslated"]
