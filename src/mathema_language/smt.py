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
from collections.abc import Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import PurePath
from typing import Any

from ._missing import MissingLibrary
from .schema.model import NO_DEFAULT, Constraints, Field, RowSchema
from .text import _regular as _rx
from .text._algebra import _MAX_CODE, _cs_has, _cs_inter, _cs_union, _re_sets
from .text._regular import _Regex

#: a field by its path: the names from the top record down to the field
FieldPath = tuple[str, ...]

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
        MissingLibrary: z3 is not installed (the optional `[smt]` extra).
    """
    try:
        import z3
    except ImportError as e:
        raise MissingLibrary("an inclusion", "z3", "smt", verb="is decided with") from e
    return z3


class MembershipEncoding:
    """One z3 encoding of the field values of two schemas."""

    def __init__(self, z3: Any) -> None:
        self.z3 = z3
        # the finest scale any decimal field of the question has; see `_decimal_digits`
        self.decimal_scale = 0
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
        self.vars: dict[FieldPath, Any] = {}
        self.extra: list[Any] = []
        self.no_surrogates = ""
        # how the library validating the record in hand reads a pattern, when that is known
        self.pattern_mode = ""
        # whether the record in hand is validated by pydantic
        self.pydantic = False

    def var(self, name: str) -> Any:
        """The z3 variable of the field `name` names, as `field_names`
        names fields (`_spell`)."""
        path = _parse(name)
        if path not in self.vars:
            self.vars[path] = self.z3.Const(f"f_{len(self.vars)}_{_label(path)}", self.V)
        return self.vars[path]

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

            Over one question, every decimal is read as a whole number `m` over `10**S`, `S` the
            finest scale of any decimal in the question (`decimal_scale`). A real with at most
            `scale` places is then an `m` divisible by `10**(S - scale)`, and it has at most
            `precision` digits when `m` lies strictly between `-10**(precision + S - scale)` and
            `10**(precision + S - scale)`. Every side states it the same way, so the solver only
            compares divisibility and bounds on integers.
        """
        z3 = self.z3
        shift = 10 ** scale
        bound = 10 ** precision if precision is not None else None
        n = V.iv(x) * shift
        on_int = z3.And(n < bound, n > -bound) if bound is not None else z3.BoolVal(True)
        top = max(self.decimal_scale, scale)
        scaled = V.rv(x) * 10 ** top
        m = z3.ToInt(scaled)
        on_real = [V.is_r(x), z3.ToReal(m) == scaled, m % 10 ** (top - scale) == 0]
        if bound is not None:
            limit = bound * 10 ** (top - scale)
            on_real += [m < limit, m > -limit]
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
            admits no more than the older, whichever of the two a library runs. Inside a record
            whose library is known to read a pattern one way (`pattern_mode`), both sides are
            that reading, so a pattern is the same language on the two sides.
        """
        if self.pattern_mode:
            return _pattern_regex(self.z3, pattern, 0, self.pattern_mode, side)
        if side == "newer":
            return _pattern_regex(self.z3, pattern, 0, "fullmatch", "newer")
        return _pattern_regex(self.z3, pattern, 0, "search", "older")

    def member(self, f: Field, x: Any, side: str, mapping: bool, D: Any = None,
               path: str | None = None) -> Any:
        """The formula: `x` is a value field `f` admits. `side` is
        `older` (admit at least what the library admits) or `newer`
        (admit at most). With `D`, `x` is a list item of that type.
        `path` is the field's name as `field_names` gives it; a nested
        record's fields are variables of their own under it
        (`body.sku`), and `x` itself only says whether the record is
        there."""
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
        if getattr(c, "pattern", None) is not None:
            raise Untranslated(f"the picture pattern on the field .{f.name}, which this encoding does not read")
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
            if t.base == "decimal" and (t.precision is None) != (t.scale is None):
                raise Untranslated(f"the decimal .{f.name} with one of its two digit limits")
            if t.base == "decimal" and t.scale is not None:
                num.append(self._decimal_digits(x, V, t.scale, t.precision, side, f.name))
                if self.pydantic and t.precision == t.scale:
                    # pydantic refuses a number written with no point here, zero included:
                    # the int arm holds those, the real arm a zero written as 0.0
                    num.append(z3.Not(V.is_i(x)))
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
            constrained = c.min_len is not None or c.max_len is not None or c.regex is not None
            if self.no_surrogates == "every" or (self.no_surrogates and constrained):
                conds.append(z3.InRe(s, z3.Star(z3.Union(
                    z3.Range(_z3_text(z3, "\x00"), _z3_text(z3, "\ud7ff")),
                    z3.Range(_z3_text(z3, "\ue000"), _z3_text(z3, chr(_Z3_MAX_CHAR)))))))
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
                child = _spell((*_parse(path), sub.name))
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
            k = z3.Int(f"k_{len(self.extra)}_{_label((f.name,))}")
            self.extra.append(k)
            item = Field("item", item_t, nullable=f.type.nullable_items,
                         constraints=t.item_constraints or Constraints())
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

    def decode(self, model: Any, language: Any, names: Sequence[str]) -> dict[str, Any]:
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
        states none, as `L[path]` and `L[path, within ("/root")]` are)."""
        pattern = getattr(language, "pattern", None)
        if not isinstance(pattern, (str, re.Pattern)):
            raise Untranslated(f"{getattr(language, 'name', language)!r}, which states no pattern")
        return _pattern(self.z3, pattern, getattr(language, "flags", 0),
                        getattr(language, "mode", "fullmatch"), x, side)

    def language(self, language: Any, names: Sequence[str], side: str) -> Any:
        """The formula: the values of `names` (fields named as
        `field_names` names them) make a member of `language`, one of its
        shapes when it has several (a command line's subcommands)."""
        paths = [_parse(name) for name in names]
        shapes = []
        for b in _branches(language):
            # pydantic encodes a str it holds to a length, a pattern or a str_ setting, and
            # refuses one holding a surrogate, so such text is in neither side of those fields
            self.no_surrogates = ""
            if b.ecosystem.name == "pydantic":
                config = getattr(b.ecosystem.model, "model_config", None) or {}
                self.no_surrogates = "every" if any(k.startswith("str_") for k in config) \
                    else "constrained"
            # the jsonschema validator reads `pattern` by `re.search`
            self.pattern_mode = "search" if b.ecosystem.name == "jsonschema" else ""
            self.pydantic = b.ecosystem.name == "pydantic"
            try:
                shape = self.row(b.schema, names, side, _SUPPORTED[b.ecosystem.name])
            finally:
                self.no_surrogates = ""
                self.pattern_mode = ""
                self.pydantic = False
            # the text of a path a converter builds is never empty
            # (`Path("")` is `.`), so neither is the text the encoding holds
            for dest, convert in (getattr(b.ecosystem, "converters", None) or {}).items():
                if (dest,) in paths and \
                        getattr(convert, "__name__", "") in _TEXT_CONVERTERS - {"str"}:
                    x = self.var(_spell((dest,)))
                    shape = self.z3.And(shape, self.z3.Implies(
                        self.V.is_s(x), self.z3.Length(self.V.sv(x)) >= 1))
            shapes.append(shape)
        formula = shapes[0] if len(shapes) == 1 else self.z3.Or(*shapes)
        # a nested field is there only when the record holding it is
        nested = [self.z3.Implies(self.var(_spell(p[:-1])) != self.V.b(self.z3.BoolVal(True)),
                                  self.V.is_absent(self.var(_spell(p))))
                  for p in paths if len(p) > 1]
        return self.z3.And(formula, *nested) if nested else formula

    def row(self, schema: RowSchema, names: Sequence[str], side: str, mapping: bool) -> Any:
        """The formula: the values of `names` (fields named as
        `field_names` names them) make a record `schema` admits."""
        z3, V = self.z3, self.V
        if schema.checks:
            raise Untranslated(f"a check of {schema.name}'s own")
        own = {(f.name,) for f in schema.fields}
        conds = [self.member(f, self.var(_spell((f.name,))), side, mapping,
                             path=_spell((f.name,)))
                 for f in schema.fields]
        for name in names:
            path = _parse(name)
            if path in own or len(path) > 1:
                continue
            x = self.var(name)
            # an exact record refuses a key it does not declare; an open one admits it, as a
            # mapping or, for a class, by leaving it out of the record it builds (`_admits`)
            if schema.column_policy == "exact":
                conds.append(V.is_absent(x))
        return z3.And(*conds) if conds else z3.BoolVal(True)


# -- regular expressions ------------------------------------------------------
#
# A Python pattern, its flags and a mode are translated by `text._regular` into
# an expression over every Python character; here it is written as a z3
# regular expression.
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

def _class_chars(pattern: str, flags: int = 0) -> tuple[tuple[int, int], ...]:
    """Intent:
        Returns the code points a pattern of one one-character item matches under `flags`.

    Raises:
        Untranslated: the pattern is not one such item.
    """
    try:
        return _rx._class_chars(pattern, flags)
    except _rx.NotRegular as e:
        raise Untranslated(str(e)) from e


_REGEX_CACHE: dict[tuple[Any, int], _Regex] = {}


def _translated(pattern: Any, flags: int) -> _Regex:
    """Intent:
        Returns the pieces of `pattern` under `flags`, translated once per pattern.

    Raises:
        Untranslated: the pattern holds a construct the translation does not read.
    """
    key = (pattern, int(flags))
    if key not in _REGEX_CACHE:
        try:
            _REGEX_CACHE[key] = _Regex(pattern, int(flags), native=True)
        except _rx.NotRegular as e:
            raise Untranslated(str(e)) from e
    return _REGEX_CACHE[key]


def _z3_text(z3: Any, text: str) -> Any:
    """Intent:
        Returns `text` as a z3 string, every character written as its code point so that none
        is read as part of an escape.
    """
    return z3.StringVal("".join(f"\\u{{{ord(c):x}}}" for c in text))


def _text_of(model: Any, x: Any) -> str:
    """Intent:
        Returns the Python string a z3 model gives the string `x`, read one code point at a
        time.
    """
    import z3
    n = model.eval(z3.Length(x), model_completion=True).as_long()
    return "".join(chr(model.eval(z3.StrToCode(z3.SubString(x, i, 1)), model_completion=True)
                       .as_long()) for i in range(n))


def _to_z3(z3: Any, r: tuple[Any, ...], side: str, alphabet: Any = None) -> Any:
    """Intent:
        Returns `r` as a z3 regular expression, each character set read on `side`, and, given
        an `_Alphabet`, written over its representatives.
    """
    R = z3.ReSort(z3.StringSort())
    memo: dict[int, Any] = {}

    def char(code: int) -> Any:
        return _z3_text(z3, chr(code))

    def go(node: tuple[Any, ...]) -> Any:
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
        reps: dict[tuple[bool, ...], int] = {}
        self.rep_at: list[int] = []
        for start in self.starts:
            key = tuple(self._has(s, starts, start) for s, starts in zip(sets, starts_of, strict=True))
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
    r"""Intent:
        Returns whether z3 finds the string `text` in the translation of
        `re.<mode>(pattern, ., flags)` on `side`, asked over the atoms of the pattern's own
        sets, a character past U+2FFFF read as U+2FFFF.

    Claims:
        end_anchor_agrees_with_re: let runs = mathema_language.smt._runs, for text in {"", "a", "\n", "aa", "a\n", "\na", "\n\n", "aaa", "aa\n", "a\na", "a\n\n", "\naa", "\na\n", "\n\na", "\n\n\n"}, f("a$", 0, "search", "older", text) == runs("a$", 0, "search", text)
        fullmatch_agrees_with_re: let runs = mathema_language.smt._runs, for text in {"", "a", "b", "c", "aa", "ab", "ac", "ba", "bb", "bc", "ca", "cb", "cc", "aaa", "aab", "aac", "aba", "abb", "abc", "aca", "acb", "acc", "baa", "bab", "bac", "bba", "bbb", "bbc", "bca", "bcb", "bcc", "caa", "cab", "cac", "cba", "cbb", "cbc", "cca", "ccb", "ccc"}, f("^a(?:b|c)*", 0, "fullmatch", "newer", text) == runs("^a(?:b|c)*", 0, "fullmatch", text)
        ignorecase_agrees_with_re: let runs = mathema_language.smt._runs, for text in {"", "a", "A", "1", "aa", "aA", "a1", "Aa", "AA", "A1", "1a", "1A", "11", "aaa", "aaA", "aa1", "aAa", "aAA", "aA1", "a1a", "a1A", "a11", "Aaa", "AaA", "Aa1", "AAa", "AAA", "AA1", "A1a", "A1A", "A11", "1aa", "1aA", "1a1", "1Aa", "1AA", "1A1", "11a", "11A", "111"}, f("[a-z]+", 2, "match", "older", text) == runs("[a-z]+", 2, "match", text)
        multiline_agrees_with_re: let runs = mathema_language.smt._runs, for text in {"", "a", "b", "\n", "aa", "ab", "a\n", "ba", "bb", "b\n", "\na", "\nb", "\n\n", "aaa", "aab", "aa\n", "aba", "abb", "ab\n", "a\na", "a\nb", "a\n\n", "baa", "bab", "ba\n", "bba", "bbb", "bb\n", "b\na", "b\nb", "b\n\n", "\naa", "\nab", "\na\n", "\nba", "\nbb", "\nb\n", "\n\na", "\n\nb", "\n\n\n"}, f("^b$", 8, "search", "newer", text) == runs("^b$", 8, "search", text)

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
    return bool(answer == z3.sat)


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

    Notes:
        A Unicode class is hundreds of ranges (`\\w` about 770), and z3's cost on a repeat of
        one grows quickly with their number: `([^\\n]\\W){0,2}` takes z3 about a minute on
        one character, past its own timeout. A question about pattern languages alone is
        asked over the atoms of their sets instead (`_squeezed`), with the same answer.
    """
    return z3.InRe(x, _pattern_regex(z3, pattern, flags, mode, side))


def _exact(pattern: Any, flags: int = 0) -> bool:
    r"""Intent:
        Returns whether the two sides of the translation of `pattern` coincide: whether every
        character set it names treats the code points above U+2FFFF as it treats U+2FFFF.

    Claims:
        refuses_a_backreference: raises(f("(a)\\1", 0), Untranslated)
        refuses_a_named_backreference: raises(f("(?P<n>a)(?P=n)", 0), Untranslated)
        refuses_a_lookahead: raises(f("(?=a)b", 0), Untranslated)
        refuses_a_lookbehind: raises(f("(?<=a)b", 0), Untranslated)
        refuses_a_conditional: raises(f("(a)?(?(1)b|c)", 0), Untranslated)
        refuses_an_atomic_group: raises(f("(?>a)", 0), Untranslated)
        refuses_a_possessive_repeat: raises(f("a*+a", 0), Untranslated)
        refuses_an_open_class: raises(f("[a", 0), Untranslated)
        refuses_reversed_bounds: raises(f("a{2,1}", 0), Untranslated)
        anchors_are_exact: f("^(?:a|b$)c?$", 8) == True
        a_negated_class_is_exact: f("[^a-z]+", 2) == True
        end_of_string_is_exact: f("\\Aa\\Z", 0) == True
        digits_are_exact: f("\\d+", 0) == True
        words_split_past_z3_characters: f("\\w", 0) == False
        a_character_past_z3_is_not_exact: f("[\\U00030000]", 0) == False

    Raises:
        Untranslated: the pattern holds a construct the translation does not read, named.
    """
    return all(_cs_exact(s) for s in _translated(pattern, flags).sets())


def _runs(pattern: Any, flags: int, mode: str, text: str) -> bool:
    """Intent:
        Returns whether `re.<mode>(pattern, text, flags)` finds a match.
    """
    return getattr(re, mode)(pattern, text, flags) is not None


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


def _converting_model(language: Any) -> str | None:
    """Intent:
        Names a shape of `language` that is a pydantic model in lax mode with a field that is
        not text, at any depth, or returns None: such a model admits input of other kinds (the
        text "1" for an int) by converting it.
    """
    def converts(fields: Any) -> bool:
        for f in fields or ():
            t = f.type
            if t.base == "struct":
                if converts(t.fields):
                    return True
            elif t.base == "list":
                if t.item is not None and (t.item.base != "string" or
                                           converts(getattr(t.item, "fields", None))):
                    return True
            elif t.base != "string":
                return True
        return False
    for b in _branches(language):
        if b.ecosystem.name != "pydantic":
            continue
        config = getattr(b.ecosystem.model, "model_config", None) or {}
        if not config.get("strict") and converts(b.schema.fields):
            return str(b.name)
    return None


def _type_decimal_scale(t: Any, seen: set[int]) -> int:
    """Intent:
        Returns the finest scale of any decimal in type `t`, nested records, items and map
        parts included, or 0.
    """
    if t is None or id(t) in seen:
        return 0
    seen.add(id(t))
    here = t.scale if t.base == "decimal" and t.scale is not None else 0
    parts = [t.item, t.key, t.value, *(f.type for f in t.fields or ())]
    return max([here, *(_type_decimal_scale(u, seen) for u in parts)])


def _decimal_scale(*languages: Any) -> int:
    """Intent:
        Returns the finest scale of any decimal field of the languages' shapes, or 0.
    """
    seen: set[int] = set()
    return max([0, *(_type_decimal_scale(f.type, seen)
                     for language in languages for b in _branches(language)
                     for f in b.schema.fields)])


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


def _schema_paths(fields: Any, prefix: FieldPath) -> list[FieldPath]:
    """Intent:
        Returns the path of every field of `fields` under `prefix`, a nested record's fields
        after the record's own.
    """
    out: list[FieldPath] = []
    for f in fields or ():
        path = (*prefix, f.name)
        out.append(path)
        if f.type.base == "struct":
            out.extend(_schema_paths(f.type.fields, path))
    return out


def _paths(language: Any) -> list[FieldPath]:
    """Intent:
        Returns the path of every field of a language's shapes once, in the order of
        `field_names`.
    """
    out = [p for branch in _branches(language) for p in _schema_paths(branch.schema.fields, ())]
    return list(dict.fromkeys(out))


def _spell(path: FieldPath) -> str:
    """Intent:
        Returns the name of the field at `path`: its names from the top record down, each with
        its backslashes and dots preceded by a backslash, joined by dots. A field whose names
        hold neither is named as before (`x`, `x.qty`); two different fields never share a
        name.
    """
    return ".".join(part.replace("\\", "\\\\").replace(".", "\\.") for part in path)


def _parse(name: str) -> FieldPath:
    """Intent:
        Returns the path a field's name names: the inverse of `_spell`, read the same way
        whatever has been read before.
    """
    parts: list[str] = []
    part: list[str] = []
    escaped = False
    for c in name:
        if escaped:
            part.append(c)
            escaped = False
        elif c == "\\":
            escaped = True
        elif c == ".":
            parts.append("".join(part))
            part = []
        else:
            part.append(c)
    parts.append("".join(part))
    return tuple(parts)


def _label(path: FieldPath) -> str:
    """Intent:
        Returns a label for the z3 variable of `path` written in identifier characters only, so
        a solver's text form reads back: a part that is an ASCII identifier as itself, any other
        as `u` and the hex of its UTF-8. The variable's number, not its label, keeps it apart
        from the others.
    """
    return "_".join(part if part.isascii() and part.isidentifier()
                    else "u" + part.encode("utf-8", "surrogatepass").hex() for part in path)


def field_names(language: Any) -> list[str]:
    """Every field of a language once, a nested record's fields after
    the record's own: the variables an encoding of the language uses,
    and the union two languages share when one is checked against the
    other. A field is named by its names from the top record down, each
    with its backslashes and dots preceded by a backslash, joined by
    dots: `x`, `x.qty`, and `a\\.b` for a field of the top record named
    `a.b`."""
    return [_spell(p) for p in _paths(language)]


def _field_at(language: Any, name: str) -> Field | None:
    """Intent:
        Returns the field a name (`field_names`) names in any of the language's shapes, or None.
    """
    fields: Any = [f for b in _branches(language) for f in b.schema.fields]
    found = None
    for part in _parse(name):
        found = next((f for f in fields if f.name == part), None)
        if found is None:
            return None
        fields = found.type.fields or ()
    return found


def _nest(language: Any, values: dict[str, Any]) -> dict[str, Any]:
    """Intent:
        Returns values keyed by field name (`field_names`) as the nested record they describe: a
        record that is there holds its fields, one that is null is None. The values are copied:
        nothing of `values` is changed.
    """
    import copy
    at = {_parse(name): copy.deepcopy(value) for name, value in values.items()}
    out: dict[str, Any] = {}
    for path in sorted(at, key=len):
        f = _field_at(language, _spell(path))
        value = {} if f is not None and f.type.base == "struct" and at[path] is True \
            else at[path]
        *parents, last = path
        holder: Any = out
        for part in parents:
            holder = holder.get(part) if isinstance(holder, dict) else None
        if isinstance(holder, dict):
            holder[last] = value
    return out


def _one_digit_limit(fields: Any, prefix: str) -> str | None:
    """Intent:
        Returns the dotted path of the first decimal field, nested ones and list items included,
        that states a precision with no scale or a scale with no precision, or None.
    """
    for f in fields or ():
        path = f"{prefix}.{f.name}"
        for t in (f.type, f.type.item, f.type.key, f.type.value):
            if t is None:
                continue
            if t.base == "decimal" and (t.precision is None) != (t.scale is None):
                return path
            found = _one_digit_limit(t.fields, path) if t.fields else None
            if found:
                return found
    return None


def untranslated(language: Any, shape: list[str] | None = None) -> str | None:
    """Why a language's records cannot be encoded, or None.

    Notes:
        A shape the encoding reads roughly but not exactly (an optional union outside the one
        form read, constraints at two levels of a pydantic field, a field-level `strict`) is a
        reason for `shape` when a list is given, and the language is still encoded; with none
        given it is returned as a reason like any other.
    """
    if language is not None and getattr(language, "branches", None):
        for branch in language.branches:
            why = untranslated(branch, shape)
            if why:
                return why
        return None
    ecosystem = getattr(language, "ecosystem", None)
    schema = getattr(language, "schema", None)
    if language is None or ecosystem is None or schema is None:
        return f"{getattr(language, 'name', language)!r} is not a record language"
    if ecosystem.name not in _SUPPORTED:
        return f"{language.name}: {ecosystem.name} records are not read by the encoding yet"
    halved = _one_digit_limit(schema.fields, "")
    if halved:
        return (f"{language.name}: the decimal {halved} has one of its two digit limits (a "
                "precision with no scale, or a scale with no precision), which the encoding "
                "does not read")
    if ecosystem.name == "pydantic":
        decorators = getattr(ecosystem.model, "__pydantic_decorators__", None)
        if decorators is not None and (decorators.field_validators or decorators.model_validators):
            return f"{language.name}: a custom validator"
        unread = _unread_pydantic(ecosystem.model, schema, shape=shape)
        if unread:
            return f"{language.name}: {unread}"
        python_engine = _reads_patterns_with_re(ecosystem.model)
        for path, pattern, nested in _patterns(schema.fields, ""):
            if python_engine and not nested:
                continue
            differs = _rust_reads_differently(pattern)
            if differs:
                return (f"{language.name}: the pattern {pattern!r} on {path} ({differs}; pydantic "
                        "validates patterns with the rust regex engine, which is not shown to "
                        "read this as Python's re does, unless the model sets "
                        "regex_engine='python-re')")
    if ecosystem.name == "argparse":
        for dest, convert in (getattr(ecosystem, "converters", None) or {}).items():
            if dest in {f.name for f in schema.fields} \
                    and getattr(convert, "__name__", "") not in _TEXT_CONVERTERS:
                return f"{language.name}: the type {getattr(convert, '__name__', convert)!r} of {dest}"
    if ecosystem.name == "jsonschema":
        keywords = _unread_keywords(ecosystem.schema)
        if keywords:
            return f"{language.name}: the JSON Schema keyword {sorted(keywords)[0]!r}"
        shapes = _shape_keywords(ecosystem.schema)
        if shapes and shape is None:
            return f"{language.name}: the JSON Schema keyword {sorted(shapes)[0]!r}"
        if shapes and shape is not None:
            shape.append(f"{language.name}: the JSON Schema keyword {sorted(shapes)[0]!r}")
    return None


def _reads_patterns_with_re(model: Any) -> bool:
    """Intent:
        Returns whether a pydantic model validates its patterns with Python's `re`: its
        configuration sets `regex_engine='python-re'` and the installed pydantic knows the
        setting (2.5 or later; an earlier one ignores it and keeps the rust engine).
    """
    config = getattr(model, "model_config", None) or {}
    if config.get("regex_engine") != "python-re":
        return False
    try:
        import pydantic
        major, minor = (int(part) for part in pydantic.VERSION.split(".")[:2])
    except (ImportError, ValueError):
        return False
    return (major, minor) >= (2, 5)


def _patterns(fields: Any, prefix: str) -> list[tuple[str, str, bool]]:
    """Intent:
        Returns every pattern a record's fields state, with the dotted path of its field and
        whether the field lies inside a nested record or a list.
    """
    out = []
    for f in fields or ():
        path = f"{prefix}.{f.name}"
        regex = getattr(f.constraints, "regex", None)
        if regex is not None:
            out.append((path, regex, bool(prefix)))
        for t in (f.type, f.type.item, f.type.key, f.type.value):
            if t is not None and t.fields:
                out.extend((p, r, True) for p, r, _ in _patterns(t.fields, path))
    return out


#: the escapes Python's re and the rust regex engine read as the same character or assertion
_SHARED_ESCAPES = set(".^$*+?()[]{}|\\-/") | set("ntrfvxuUA")


def _rust_reads_differently(pattern: str) -> str | None:
    """Intent:
        Names the first construct of `pattern` that the rust regex engine is not shown to read
        as Python's `re` does, or returns None when every construct is one both read alike:
        literal characters, `.`, classes of literals and ranges, groups, alternation, greedy and
        lazy repeats, `^`, `\\A`, and `$`.

    Notes:
        `$` is the end of the text alone in rust and also before a final newline in Python;
        the encoding's two sides already bracket both (a search that allows the newline on the
        older side, a full match on the newer). The classes `\\s` and `\\w` hold different
        characters in the two engines, `\\b` follows `\\w`, `\\<` and `\\>` are word edges in
        rust and literals in Python, and inside a class rust reads `&&`, `--`, `~~` and a
        nested `[` as set operations where Python reads literals. `\\d` and the inline flags
        are refused as not shown to agree.
    """
    parser, _, _ = _rx._sre()
    try:
        parsed = parser.parse(pattern)
    except (re.error, ValueError, TypeError) as e:
        return f"it does not compile ({e})"
    if parsed.state.flags & (re.IGNORECASE | re.MULTILINE | re.DOTALL | re.VERBOSE | re.ASCII):
        return "an inline flag"
    in_class, i = False, 0
    while i < len(pattern):
        c = pattern[i]
        if c == "\\":
            following = pattern[i + 1:i + 2]
            if following not in _SHARED_ESCAPES:
                return f"the escape \\{following}"
            i += 2
            continue
        if in_class:
            if c == "[":
                return "a [ inside a class"
            if c in "&-~" and pattern[i + 1:i + 2] == c:
                return f"{c}{c} inside a class"
            in_class = c != "]"
        elif c == "[":
            in_class = True
            i += 2 if pattern[i + 1:i + 2] == "^" else 1
            if pattern[i:i + 1] == "]":
                return "a class starting with ]"
            continue
        i += 1

    def walk(items: Any) -> str | None:
        for op, arg in items:
            name = str(op)
            if name in ("LITERAL", "NOT_LITERAL", "ANY"):
                continue
            if name == "IN":
                odd = [str(o) for o, _ in arg if str(o) not in ("LITERAL", "RANGE", "NEGATE")]
                if odd:
                    return f"a class holding a {odd[0].lower()}"
            elif name in ("MAX_REPEAT", "MIN_REPEAT"):
                found = walk(arg[2])
                if found:
                    return found
            elif name == "SUBPATTERN":
                if arg[1] or arg[2]:
                    return "a scoped flag"
                found = walk(arg[3])
                if found:
                    return found
            elif name == "BRANCH":
                for branch in arg[1]:
                    found = walk(branch)
                    if found:
                        return found
            elif name == "AT" and str(arg) in ("AT_BEGINNING", "AT_BEGINNING_STRING", "AT_END"):
                continue
            else:
                return {"POSSESSIVE_REPEAT": "a possessive repeat", "GROUPREF": "a backreference",
                        "ATOMIC_GROUP": "an atomic group", "ASSERT": "a lookaround",
                        "ASSERT_NOT": "a lookaround", "AT": f"the assertion {arg}",
                        "CATEGORY": "a character category"}.get(name, name.lower())
        return None

    return walk(parsed)


#: the pydantic field metadata the adaptor reads into the neutral model,
#: by marker type; settings that only loosen or only tighten coercion are
#: read as no constraint, which the encoding's sides already allow for
_PYDANTIC_MARKERS = {"Gt", "Ge", "Lt", "Le", "MinLen", "MaxLen", "MultipleOf", "Strict"}
_PYDANTIC_SETTINGS = {"pattern", "max_digits", "decimal_places"}


def _pydantic_models(annotation: Any) -> list[Any]:
    """Intent:
        Returns the pydantic models an annotation holds: itself, or those inside an optional,
        a union, a list or another generic.
    """
    import typing
    try:
        from pydantic import BaseModel
    except ImportError:  # pragma: no cover -- a pydantic language needs pydantic
        return []
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]
    return [m for arg in typing.get_args(annotation) for m in _pydantic_models(arg)]


def _inner_fields(t: Any) -> Any:
    """Intent:
        Returns the fields of the record a neutral type holds, itself or as its items.
    """
    for inner in (t, getattr(t, "item", None)):
        if inner is not None and getattr(inner, "fields", None):
            return inner.fields
    return ()


_FIELD_STRICT = ("the setting 'strict' on {at}, which differs from the strictness of its model; "
                 "strictness is read for a whole model and not per field")
def _shape(sink: list[str] | None, reason: str) -> str | None:
    """Intent:
        Records a shape decline in `sink` and returns None, or returns `reason` when there is
        no sink.
    """
    if sink is None:
        return reason
    sink.append(reason)
    return None


_STRING_TRANSFORMS = ("strip_whitespace", "to_upper", "to_lower", "ascii_only")


def _unread_marker(marker: Any, at: str, t: Any, model_strict: bool = False,
                   shape: list[str] | None = None) -> str | None:
    """Intent:
        Names what a pydantic field marker carries that the neutral model does not, or returns
        None when it is read: a bound or length marker, an `Interval`, the `StringConstraints`
        that only bound or match, a pattern, a decimal digit limit with both limits given, and
        `allow_inf_nan=False`. `t` is the neutral type of the field, or None.

    Notes:
        The same rule serves a marker in the field's own metadata and one inside an optional or
        union arm. A field-level `strict=True` is named when the model is not strict, since
        strictness is read for the model as a whole and not per field; `strict=False` and
        `strict=True` in a strict model read as the model does.
    """
    if marker is None:
        return None
    kind = type(marker).__name__
    if kind == "_PydanticGeneralMetadata":
        given = {k for k, v in vars(marker).items() if v is not None}
        if vars(marker).get("allow_inf_nan") is True:
            return (f"the setting 'allow_inf_nan' on {at}, which admits NaN and the "
                    "infinities")
        if vars(marker).get("strict") is True and not model_strict:
            return _shape(shape, _FIELD_STRICT.format(at=at))
        odd = given - _PYDANTIC_SETTINGS - {"allow_inf_nan", "strict"}
        if odd:
            return f"the setting {sorted(odd)[0]!r} on {at}"
        if given & {"max_digits", "decimal_places"} \
                and (t is None or t.precision is None or t.scale is None):
            return f"decimal digits on {at} the neutral model does not carry"
        return None
    if kind == "AllowInfNan":
        if getattr(marker, "allow_inf_nan", None) is not False:
            return (f"the setting 'allow_inf_nan' on {at}, which admits NaN and the "
                    "infinities")
        return None
    if kind == "Strict":
        if getattr(marker, "strict", None) is True and not model_strict:
            return _shape(shape, _FIELD_STRICT.format(at=at))
        return None
    if kind == "Interval":
        return None
    if kind == "StringConstraints":
        if getattr(marker, "strict", None) is True and not model_strict:
            return _shape(shape, _FIELD_STRICT.format(at=at))
        for setting in _STRING_TRANSFORMS:
            if getattr(marker, setting, None) is not None:
                return f"the setting {setting!r} on {at}"
        return None
    if kind not in _PYDANTIC_MARKERS:
        return f"the {kind} constraint on {at}"
    return None


def _unread_pydantic(model: Any, schema: Any, path: str = "", seen: Any = None,
                     shape: list[str] | None = None) -> str | None:
    """Intent:
        Names the first piece of a pydantic model's field metadata the neutral model does not
        carry, or a validator of the model's own, or returns None: the model's fields and those
        of every model a field holds (nested, optional, in a union or a list), with the neutral
        fields `schema` holds for them.

    Notes:
        A decimal with one of its two digit limits and `allow_inf_nan=True` are named; pydantic
        reads them otherwise than the encoding does. `allow_inf_nan=False` states what the
        encoding already reads, no NaN and no infinity, and is no constraint here.
    """
    seen = set() if seen is None else seen
    if model in seen:
        return None
    seen.add(model)
    if path:
        decorators = getattr(model, "__pydantic_decorators__", None)
        if decorators is not None and (decorators.field_validators or decorators.model_validators):
            return f"a custom validator on {path}"
    if path and (getattr(model, "model_config", None) or {}).get("extra") is not None:
        return f"the extra setting of the model at {path}"
    fields = {f.name: f for f in getattr(schema, "fields", schema) or ()}
    for name, info in getattr(model, "model_fields", {}).items():
        at = f"{path}.{name}"
        for alias in (getattr(info, "alias", None), getattr(info, "validation_alias", None)):
            if alias is not None and alias != name:
                return f"the alias {alias!r} of {at}, by which the model reads the field"
        from .schema.adaptors._hints import annotation_markers, flatten_markers
        own = [m for m in flatten_markers(tuple(getattr(info, "metadata", ()) or ()))
               if m is not None]
        arm = [m for m in annotation_markers(getattr(info, "annotation", None))
               if m is not None and type(m).__name__ != "NoneType"]
        if own and arm:
            both = (f"constraints on both {at} and inside its optional or union arm; "
                    "only one of the two levels is read")
            if shape is None:
                return both
            shape.append(both)
        model_strict = (getattr(model, "model_config", None) or {}).get("strict") is True
        for marker in own + arm:
            unread = _unread_marker(marker, at, fields[name].type if name in fields else None,
                                    model_strict, shape)
            if unread:
                return unread
        inner = _inner_fields(fields[name].type) if name in fields else ()
        for nested in _pydantic_models(getattr(info, "annotation", None)):
            unread = _unread_pydantic(nested, inner, at, seen, shape)
            if unread:
                return unread
    return None


def _nullable_pair(options: Any) -> bool:
    """Intent:
        Whether an `anyOf` or `oneOf` list is exactly one schema and `{"type": "null"}`, the one
        shape of either the adaptor reads (as a nullable field).
    """
    return isinstance(options, list) and len(options) == 2 \
        and sum(1 for o in options if o == {"type": "null"}) == 1 \
        and all(isinstance(o, dict) for o in options)


_ANNOTATION_KEYWORDS = {"title", "description", "default", "examples", "$comment"}
_LENGTH_KEYWORDS = {"minLength", "maxLength"}
_ITEM_KEYWORDS = {"minItems", "maxItems"}


def _union_unread(schema: dict[str, Any]) -> set[str]:
    """Intent:
        Names why a property's `anyOf` or `oneOf` is outside the one form read: one non-null
        schema and `{"type": "null"}`, alone (not with the other of the two), with no `type` or
        `const` beside it, no keyword given both on the property and in the arm, and an arm that
        does not itself admit null under `oneOf`.
    """
    out: set[str] = set()
    keys = [k for k in ("anyOf", "oneOf") if k in schema]
    if not keys:
        return out
    if len(keys) == 2:
        out.add("anyOf together with oneOf on one property")
        return out
    key = keys[0]
    if not _nullable_pair(schema[key]):
        return out
    arm = next(o for o in schema[key] if o != {"type": "null"})
    for beside in ("type", "const"):
        if beside in schema:
            out.add(f"{beside} beside a nullable {key}")
    both = (set(schema) & set(arm)) - {key} - _ANNOTATION_KEYWORDS
    out |= {f"{k} (on both a property and its {key} arm)" for k in both}
    arm_type = arm.get("type")
    if isinstance(arm_type, list) and "null" in arm_type:
        out.add(f"an {key} arm that admits null")
    if key == "oneOf" and not isinstance(arm_type, str):
        out.add("a oneOf arm with no single type, which may admit null as the null arm does")
    return out


def _length_unread(prop: dict[str, Any], arm: dict[str, Any] | None) -> set[str]:
    """Intent:
        Names a string-length keyword on an array, an item-count keyword on a string, or both
        families where the type does not say which applies.
    """
    view = {**prop, **(arm or {})}
    kind = view.get("type")
    lengths, items = set(view) & _LENGTH_KEYWORDS, set(view) & _ITEM_KEYWORDS
    if lengths and items:
        return {f"{sorted(lengths)[0]} with {sorted(items)[0]}, mixed"}
    if lengths and kind == "array":
        return {f"{sorted(lengths)[0]} on an array"}
    if items and kind == "string":
        return {f"{sorted(items)[0]} on a string"}
    return set()


def _unread_keywords(schema: Any, nested: bool = False) -> set[str]:
    """Intent:
        Returns the keywords of a JSON Schema, and of its properties, that the validator enforces
        and the neutral model does not carry.

    Notes:
        `additionalProperties` is carried at the top only, so `nested` marks a property's schema.
        An `anyOf` or `oneOf` is read only as one schema and `{"type": "null"}`; the arm is
        searched for unread keywords as a property is.
    """
    out: set[str] = set()
    if not isinstance(schema, dict):
        return out
    out |= set(schema) & _JSON_SCHEMA_ENFORCED_UNREAD
    arm: dict[str, Any] | None = None
    for key in ("anyOf", "oneOf"):
        options = schema.get(key)
        if options is not None and not _nullable_pair(options):
            out.add(key)
        elif options is not None:
            arm = next(o for o in options if o != {"type": "null"})
            out |= _unread_keywords(arm, nested=True)
    if nested and "additionalProperties" in schema and schema["additionalProperties"] is not True:
        out.add("additionalProperties (on a nested object)")
    elif isinstance(schema.get("additionalProperties"), dict) and schema["additionalProperties"]:
        out.add("additionalProperties (a schema for the keys no property names)")
    if set(schema.get("required") or ()) - set(schema.get("properties") or {}):
        out.add("required (a key no property names)")
    for prop in (schema.get("properties") or {}).values():
        out |= _unread_keywords(prop, nested=True)
    return out


_ITEM_SCALARS = {"integer", "number", "string", "boolean"}


def _items_unread(schema: dict[str, Any]) -> set[str]:
    """Intent:
        Names what the `items` of an array carries beyond `{"type": <scalar type>}` or
        `{"enum": [...]}` (and a title or description): the neutral model keeps only the item type, so any other keyword, a
        union, a reference, a nested container or a tuple form is named as `items carrying ...`.
    """
    if "items" not in schema:
        return set()
    items = schema["items"]
    if not isinstance(items, dict):
        return {"items carrying a non-schema form"}
    if items.get("type") == "string":
        return {f"items carrying {k}" for k in
                set(items) - {"type", "title", "description", "pattern", "minLength", "maxLength"}}
    if "type" not in items and "enum" in items:
        return {f"items carrying {k}" for k in set(items) - {"enum", "title", "description"}}
    extra = set(items) - {"type", "title", "description"}
    out = {f"items carrying {k}" for k in extra}
    if items.get("type") not in _ITEM_SCALARS:
        out.add(f"items carrying type {items.get('type')!r}")
    return out


def _shape_keywords(schema: Any) -> set[str]:
    """Intent:
        Returns the shapes of a JSON Schema's properties, and of their arms, that the encoding
        reads roughly and not exactly: a union outside the one form read, and string-length
        and item-count keywords the type does not match.
    """
    out: set[str] = set()
    if not isinstance(schema, dict):
        return out
    arm: dict[str, Any] | None = None
    for key in ("anyOf", "oneOf"):
        if _nullable_pair(schema.get(key)):
            arm = next(o for o in schema[key] if o != {"type": "null"})
            out |= _shape_keywords(arm)
    out |= _union_unread(schema)
    out |= _length_unread(schema, arm)
    out |= _items_unread(schema)
    for prop in (schema.get("properties") or {}).values():
        out |= _shape_keywords(prop)
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
            # a zero on the real arm is one written with a point
            if q == 0:
                return decimal.Decimal("0.0")
            return decimal.Decimal(q.numerator) / decimal.Decimal(q.denominator)
        return float(q)
    text = model.eval(D.sv(v)).as_string()
    return re.sub(r"\\u\{([0-9a-fA-F]+)\}", lambda m: chr(int(m.group(1), 16)), text)


def new_encoding(z3: Any = None) -> MembershipEncoding:
    """A fresh encoding context, one per claim: every language encoded in
    it shares one z3 variable per field name."""
    return MembershipEncoding(z3 if z3 is not None else _z3())


def build(language: Any, values: dict[str, Any]) -> Any:
    """The record `language` builds from `values`, keyed by field name
    as `field_names` names fields: the first of its shapes whose record
    it admits, else the first record a shape builds, else None when no
    shape's class builds one.
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
        `base` of `older` (keyed by field name, `field_names`), returning the points tried and the
        first record `older` admits and `newer` refuses, if any, nested as the shape of `older`
        that admits it reads it.
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
                values = {**base, _spell((f.name,)): point}
                tried.append(f".{f.name} = {point!r}")
                if _admits(older, values) and not _admits(newer, values):
                    shape = next(b for b in _branches(older) if _admits(b, values))
                    return tried, _nest(shape, values)
    return tried, None


def _schema_inclusion(older: Any, newer: Any, *, timeout_ms: int = 5000) -> _InclusionResult:
    """Intent:
        Decides whether `newer` admits every record `older` admits: `proven`, `falsified` with a
        record both validations confirm `older` admits and `newer` refuses, or `unknown`.

    Notes:
        `older` and `newer` are record languages, or anything `L[...]` resolves (a model class,
        a JSON Schema dict). A proof is followed by a run at each float bound's neighbouring
        doubles, which can still falsify it.

        The witness reported is chosen among the records both validations confirm: each text
        field in turn, in field order, takes the shortest text, and then, character by
        character, a letter before a digit before other printable ASCII before any other
        character, the lower code point within each. Fields that are not text keep the value
        the solver gave. The choice is made after a confirmed witness exists and within a time
        limit, past which the best confirmed so far is reported, so the verdict never depends
        on it.
    """
    z3 = _z3()
    from .schema.adaptors import adapt_row
    older, newer = (x if hasattr(x, "ecosystem") or getattr(x, "branches", None) else adapt_row(x)
                    for x in (older, newer))
    declined: list[str] = []
    for language in (older, newer):
        why = untranslated(language, declined)
        if why:
            return _InclusionResult("unknown", f"not translated: {why}")
    converts = _converting_model(older)
    if converts and any(b.ecosystem.name != "pydantic" for b in _branches(newer)):
        return _InclusionResult("unknown", f"not translated: {converts} converts its input to its "
                                "field types (pydantic's lax mode), which the encoding does not "
                                "read against another library's validation")
    enc = MembershipEncoding(z3)
    enc.decimal_scale = _decimal_scale(older, newer)
    names = list(dict.fromkeys([*field_names(older), *field_names(newer)]))
    # one top-level key neither side declares stands for every such key: an open record
    # admits it and a closed one refuses it, which no declared field shows
    # (only when `older` has an open shape and `newer` a closed one, the one case it decides)
    if any(b.schema.column_policy != "exact" for b in _branches(older)) and \
            any(b.schema.column_policy == "exact" for b in _branches(newer)):
        other = next(f"other_{k}" for k in range(len(names) + 1) if f"other_{k}" not in names)
        names.append(other)
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
    kept = undeclared
    if answer != z3.sat and undeclared:
        answer, kept = solver.check(), []
    if answer == z3.unknown:
        return _InclusionResult("unknown", f"z3 did not decide it ({solver.reason_unknown()})")
    if answer == z3.unsat and declined:
        return _InclusionResult("unknown", f"proof declined: {declined[0]}; searched for a "
                                "counterexample and found none")
    if answer == z3.unsat:
        base = _a_member(older)
        tried, edge = _float_line(older, newer, base)
        if edge is not None:
            return _InclusionResult("falsified", "at a float bound's neighbouring double, "
                                   f"{older.name} admits it and {newer.name} refuses it",
                                   edge, tried)
        return _InclusionResult("proven", f"every record {older.name} admits, {newer.name} admits",
                               float_line=tried)
    def read(model: Any) -> dict[str, Any]:
        found: dict[str, Any] = {}
        for name in names:
            f = _field_at(older, name) or _field_at(newer, name)
            present, value = _value(enc, model, enc.var(name), f)
            if present:
                found[name] = value
        return found

    def confirmed(found: dict[str, Any]) -> bool:
        return _admits(older, found) and not _admits(newer, found)

    first = solver.model()
    values = read(first)
    if confirmed(values):
        # every field that is not text stays as the solver first gave it
        held = [enc.var(n) == first.eval(enc.var(n), model_completion=True)
                for n in names if not isinstance(values.get(n), str)]
        values = _most_readable(enc, solver, [*kept, *held], names, values, read, confirmed)
        # the witness is nested by the shape of `older` that admits it, since two shapes may
        # read one name as a scalar and as a record
        shape = next((b for b in _branches(older) if _admits(b, values)), older)
        return _InclusionResult("falsified", f"{older.name} admits it and {newer.name} refuses it",
                               _nest(shape, values))
    if declined:
        return _InclusionResult("unknown", f"proof declined: {declined[0]}; the solver's candidate "
                                f"{values!r} was not confirmed by the validations")
    return _InclusionResult("unknown", f"z3 offered {values!r}, which the validations do not "
                           f"confirm ({older.name} must admit it and {newer.name} refuse it); "
                           "this is a gap in the encoding")


#: the seconds a search for a more readable witness may take
_WITNESS_SECONDS = 3.0

#: the characters of a witness examined one by one, from the start of each text
_WITNESS_CHARACTERS = 16

#: the ranks a witness character is preferred by, each as code point ranges in order
_READABILITY = (
    ((0x41, 0x5A), (0x61, 0x7A)),
    ((0x30, 0x39),),
    ((0x20, 0x2F), (0x3A, 0x40), (0x5B, 0x60), (0x7B, 0x7E)),
    ((0x00, 0x1F), (0x7F, _Z3_MAX_CHAR)),
)


def _most_readable(enc: MembershipEncoding, solver: Any, kept: list[Any],
                   names: Sequence[str], values: dict[str, Any], read: Any,
                   confirmed: Any) -> dict[str, Any]:
    """Intent:
        Returns the confirmed witness the rule of `_schema_inclusion` prefers to `values`, itself
        a confirmed witness: for each text field in order the shortest text, then each of its
        first characters in turn in the best readability rank and lowest code point a
        confirmed witness allows.

    Notes:
        Each step asks the solver for a witness under one more condition and keeps it only
        when both validations confirm it. A step the solver does not answer in time, or the
        time limit, ends the search with what is confirmed so far.
    """
    import time
    z3 = enc.z3
    deadline = time.monotonic() + _WITNESS_SECONDS
    best = values
    fixed = list(kept)

    def better(*conditions: Any) -> bool:
        nonlocal best
        if time.monotonic() >= deadline:
            raise TimeoutError
        answer = solver.check(*fixed, *conditions)
        if answer == z3.unknown:
            raise TimeoutError
        if answer != z3.sat:
            return False
        found = read(solver.model())
        if not confirmed(found):
            return False
        best = found
        return True

    solver.set("timeout", 250)
    try:
        for name in names:
            if not isinstance(best.get(name), str):
                continue
            x = enc.var(name)
            s = enc.V.sv(x)
            for length in range(len(best[name])):
                if better(enc.V.is_s(x), z3.Length(s) == length):
                    break
            fixed += [enc.V.is_s(x), z3.Length(s) == len(best[name])]
            for i in range(min(len(best[name]), _WITNESS_CHARACTERS)):
                code = z3.StrToCode(z3.SubString(s, i, 1))
                here = ord(best[name][i])
                for lo, hi in (span for rank in _READABILITY for span in rank):
                    if lo <= here <= hi:
                        hi = here
                    if better(code >= lo, code <= hi):
                        low, high = lo, ord(best[name][i])
                        while low < high:
                            middle = (low + high) // 2
                            if better(code >= low, code <= middle):
                                high = ord(best[name][i])
                            else:
                                low = middle + 1
                        break
                    if lo <= here <= hi:
                        break
                fixed.append(code == ord(best[name][i]))
    except TimeoutError:
        pass
    return best


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
    for regex, keep in zip(_squeezed(z3, wanted), inside, strict=True):
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
    values: dict[str, Any] = {}
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
        for part in _parse(name):
            value = value.get(part) if isinstance(value, dict) else getattr(value, part, None)
        return str(value) if isinstance(value, PurePath) else value
    return None


def _a_member(language: Any) -> dict[str, Any] | None:
    """Intent:
        Returns the top-level field values of one member the language samples with a fixed seed,
        each keyed by its field name (`field_names`), or None when it cannot sample one.
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
                out[_spell((f.name,))] = row[f.name]
        elif hasattr(row, f.name):
            out[_spell((f.name,))] = getattr(row, f.name)
    return out


__all__ = ["MembershipEncoding", "Untranslated", "build", "field_names", "new_encoding",
           "untranslated"]
