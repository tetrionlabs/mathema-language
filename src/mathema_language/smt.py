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
list, a nested record, a custom validator, a JSON Schema keyword the
adaptor does not read, a decimal with one of its two digit limits)
raises `Untranslated` naming it; `untranslated(language)` says so before
encoding. A constraint is never dropped.

Each field value is of a single z3 type holding every kind of value a
field can take: absent, null, NaN, the two infinities, a bool, an int,
an exact real and a string. Numbers are exact reals, as mathema's own
z3 rung reads them. z3's strings hold characters up to U+2FFFF; a
record whose text uses a higher one reads the same, to every pattern
and length the encoding holds, as one with that character replaced by a
character no pattern names, so a proof over z3's characters holds over
all of Unicode, and a pattern or constant that names such a character is
not translated.

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
from typing import Any

from .schema.model import NO_DEFAULT, Field, RowSchema

#: the ecosystems whose records the encoding reads, and whether a record
#: is a mapping that may leave a key out
_SUPPORTED = {"plain": True, "jsonschema": True, "attribute": False, "pydantic": False}

#: the JSON Schema keywords the adaptor reads into the neutral model;
#: `jsonschema` enforces every other one, which the encoding cannot see
_JSON_SCHEMA_READ = {
    "type", "properties", "required", "additionalProperties", "minimum", "maximum",
    "exclusiveMinimum", "exclusiveMaximum", "minLength", "maxLength", "pattern", "enum",
    "const", "multipleOf", "title", "description", "$schema", "$id", "default", "examples",
}

#: the last character z3's strings hold; a higher one is not passed to
#: z3, which would read it as the text of its escape
_Z3_MAX_CHAR = 0x2FFFF

#: the scalar types the encoding reads
_READ_BASES = {"bool", "int", "float", "decimal", "string", "categorical", "any"}


class Untranslated(Exception):
    """A construct the encoding does not read, named."""


@dataclass
class _InclusionResult:
    """`verdict` is `proven` (every record `older` admits, `newer`
    admits), `falsified` (with `witness`, a record `older` admits and
    `newer` refuses, confirmed by both validations) or `unknown` (with
    `reason`). `float_line` lists the neighbouring doubles of each float
    bound that were run through both validations, and holds the first
    one `older` admits and `newer` refuses, if any."""
    verdict: str
    reason: str = ""
    witness: dict[str, Any] | None = None
    float_line: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.verdict == "falsified":
            return f"falsified   {self.witness}: {self.reason}"
        return f"{self.verdict}   {self.reason}".rstrip()


def _z3() -> Any:
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
        v = z3.Datatype("Value")
        for tag in ("absent", "null", "nan", "pinf", "ninf"):
            v.declare(tag)
        v.declare("b", ("bv", z3.BoolSort()))
        v.declare("i", ("iv", z3.IntSort()))
        v.declare("r", ("rv", z3.RealSort()))
        v.declare("s", ("sv", z3.StringSort()))
        self.V = v.create()
        self.vars: dict[str, Any] = {}
        self.extra: list[Any] = []

    def var(self, name: str) -> Any:
        if name not in self.vars:
            self.vars[name] = self.z3.Const(f"f_{len(self.vars)}_{name}", self.V)
        return self.vars[name]

    def const(self, value: Any) -> Any:
        """A Python value as a z3 Value."""
        V = self.V
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
        q = Fraction(value)
        return self.z3.RealVal(f"{q.numerator}/{q.denominator}")

    def _number(self, x: Any) -> tuple[Any, Any]:
        """`(is a finite number, its real value)`."""
        V = self.V
        return (self.z3.Or(V.is_i(x), V.is_r(x)),
                self.z3.If(V.is_i(x), self.z3.ToReal(V.iv(x)), V.rv(x)))

    def _bounds(self, f: Field, real: Any) -> list[Any]:
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
        """`pattern` as a z3 regular expression: a full match on the
        newer side, a search (anything around it) on the older side."""
        z3 = self.z3
        regex = _Regex(z3, widen=side == "older")
        body = regex.translate(pattern)
        if side == "newer":
            return body
        anything = z3.Star(z3.AllChar(z3.ReSort(z3.StringSort())))
        parts = [body]
        if not regex.anchored_start:
            parts.insert(0, anything)
        # `$` also matches before a final newline
        parts.append(z3.Option(z3.Re(z3.StringVal("\n"))) if regex.anchored_end else anything)
        return z3.Concat(*parts)

    def member(self, f: Field, x: Any, side: str, mapping: bool) -> Any:
        """The formula: `x` is a value field `f` admits. `side` is
        `older` (admit at least what the library admits) or `newer`
        (admit at most)."""
        z3, V, c, t = self.z3, self.V, f.constraints, f.type
        options = []
        if mapping and not f.required:
            options.append(V.is_absent(x))
        if f.nullable:
            options.append(V.is_null(x))
        if t.base not in _READ_BASES:
            raise Untranslated(f"the {t.base} field .{f.name}")
        if t.base == "any":
            if side == "newer":
                raise Untranslated(f"the field .{f.name} of no type the encoding reads")
            options.append(z3.Not(V.is_absent(x)))
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
            is_num, real = self._number(x)
            num = [is_num, *self._bounds(f, real)]
            if c.multiple_of is not None:
                raise Untranslated(f"the divisor on the {t.base} field .{f.name}")
            if t.base == "decimal" and t.scale is not None:
                k = z3.Int(f"k_{len(self.extra)}_{f.name}")
                self.extra.append(k)
                num.append(real * (10 ** t.scale) == z3.ToReal(k))
                if t.precision is not None:
                    num += [k < 10 ** t.precision, k > -(10 ** t.precision)]
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
        elif t.base == "categorical":
            conds.append(z3.Or(*[x == self.const(level) for level in (t.levels or ())]) if t.levels
                         else z3.BoolVal(False))
        if c.enum is not None:
            conds.append(z3.Or(*[x == self.const(e) for e in c.enum]) if c.enum else z3.BoolVal(False))
        if c.const is not NO_DEFAULT:
            conds.append(x == self.const(c.const))
        options.append(z3.And(*conds))
        return z3.Or(*options)

    def row(self, schema: RowSchema, names: list[str], side: str, mapping: bool) -> Any:
        """The formula: the values of `names` make a record `schema`
        admits."""
        z3, V = self.z3, self.V
        if schema.checks:
            raise Untranslated(f"a check of {schema.name}'s own")
        own = {f.name for f in schema.fields}
        conds = [self.member(f, self.var(f.name), side, mapping) for f in schema.fields]
        for name in names:
            if name in own:
                continue
            x = self.var(name)
            if not mapping or schema.column_policy == "exact":
                conds.append(V.is_absent(x))
        return z3.And(*conds) if conds else z3.BoolVal(True)


class _Regex:
    """A Python regular expression as a z3 one, for the constructs both
    read the same way; anything else is `Untranslated`."""

    def __init__(self, z3: Any, widen: bool = False) -> None:
        self.z3 = z3
        self.R = z3.ReSort(z3.StringSort())
        self.widen = widen
        self.anchored_start = False
        self.anchored_end = False

    def translate(self, pattern: str) -> Any:
        import sys
        if sys.version_info >= (3, 11):
            from re import _parser as sre_parse  # type: ignore[attr-defined]
        else:
            import sre_parse
        try:
            parsed = sre_parse.parse(pattern)
        except re.error as e:
            raise Untranslated(f"the pattern {pattern!r}, which does not compile") from e
        items = list(parsed)
        if items and str(items[0][0]) == "AT" and str(items[0][1]) in ("AT_BEGINNING", "AT_BEGINNING_STRING"):
            self.anchored_start = True
            items = items[1:]
        if items and str(items[-1][0]) == "AT" and str(items[-1][1]) in ("AT_END", "AT_END_STRING"):
            self.anchored_end = True
            items = items[:-1]
        return self._seq(items, pattern)

    def _seq(self, items: Any, pattern: str) -> Any:
        z3 = self.z3
        parts = [self._item(op, arg, pattern) for op, arg in items]
        parts = [p for p in parts if p is not None]
        if not parts:
            return z3.Re(z3.StringVal(""))
        return parts[0] if len(parts) == 1 else z3.Concat(*parts)

    def _item(self, op: Any, arg: Any, pattern: str) -> Any:
        z3, name = self.z3, str(op)
        if name == "LITERAL":
            return z3.Re(z3.StringVal(self._char(arg, pattern)))
        if name == "NOT_LITERAL":
            return z3.Diff(z3.AllChar(self.R), z3.Re(z3.StringVal(self._char(arg, pattern))))
        if name == "ANY":
            return z3.Diff(z3.AllChar(self.R), z3.Re(z3.StringVal("\n")))
        if name == "IN":
            return self._class(arg, pattern)
        if name in ("MAX_REPEAT", "MIN_REPEAT", "POSSESSIVE_REPEAT"):
            lo, hi, sub = arg
            inner = self._seq(sub, pattern)
            if hi == sre_maxrepeat():
                return z3.Concat(z3.Loop(inner, lo, lo), z3.Star(inner)) if lo else z3.Star(inner)
            return z3.Loop(inner, lo, hi)
        if name == "SUBPATTERN":
            return self._seq(arg[-1], pattern)
        if name == "BRANCH":
            return z3.Union(*[self._seq(b, pattern) for b in arg[1]])
        if name == "CATEGORY":
            return self._category(str(arg), pattern)
        raise Untranslated(f"the pattern {pattern!r} ({name.lower()})")

    def _char(self, code: int, pattern: str) -> str:
        if code > _Z3_MAX_CHAR:
            raise Untranslated(f"the pattern {pattern!r}, past the characters z3 holds")
        return chr(code)

    def _category(self, name: str, pattern: str) -> Any:
        """`\\d` or `\\w`. Python reads them over all of Unicode; the ASCII
        ranges admit less, which is what the newer side needs, and the
        older side widens them to any character."""
        z3 = self.z3
        if self.widen and name in ("CATEGORY_DIGIT", "CATEGORY_WORD"):
            return z3.AllChar(self.R)
        ranges = {"CATEGORY_DIGIT": [("0", "9")],
                  "CATEGORY_WORD": [("a", "z"), ("A", "Z"), ("0", "9"), ("_", "_")]}
        if name not in ranges:
            raise Untranslated(f"the pattern {pattern!r} ({name.lower()})")
        return z3.Union(*[z3.Range(a, b) for a, b in ranges[name]]) if len(ranges[name]) > 1 \
            else z3.Range(*ranges[name][0])

    def _class(self, items: Any, pattern: str) -> Any:
        z3 = self.z3
        negate = False
        parts = []
        for op, arg in items:
            name = str(op)
            if name == "NEGATE":
                negate = True
            elif name == "LITERAL":
                parts.append(z3.Re(z3.StringVal(self._char(arg, pattern))))
            elif name == "RANGE":
                parts.append(z3.Range(self._char(arg[0], pattern), self._char(arg[1], pattern)))
            elif name == "CATEGORY":
                parts.append(self._category(str(arg), pattern))
            else:
                raise Untranslated(f"the pattern {pattern!r} ({name.lower()})")
        cls = parts[0] if len(parts) == 1 else z3.Union(*parts)
        return z3.Diff(z3.AllChar(self.R), cls) if negate else cls


def sre_maxrepeat() -> int:
    """The repeat count the regex parser uses for an unbounded repeat."""
    import sys
    if sys.version_info >= (3, 11):
        from re import _constants  # type: ignore[attr-defined]
        return int(_constants.MAXREPEAT)
    import sre_constants
    return int(sre_constants.MAXREPEAT)


def untranslated(language: Any) -> str | None:
    """Why a language's records cannot be encoded, or None."""
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
    """The first piece of pydantic field metadata the neutral model does
    not carry, named, or None."""
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


def _unread_keywords(schema: Any) -> set[str]:
    out: set[str] = set()
    if not isinstance(schema, dict):
        return out
    out |= set(schema) - _JSON_SCHEMA_READ
    for prop in (schema.get("properties") or {}).values():
        out |= _unread_keywords(prop)
    return out


def _value(enc: MembershipEncoding, model: Any, x: Any, f: Field | None) -> tuple[bool, Any]:
    """`(present, value)` for one field of z3's model."""
    z3, V = enc.z3, enc.V
    v = model.eval(x, model_completion=True)
    if z3.is_true(model.eval(V.is_absent(v))):
        return False, None
    if z3.is_true(model.eval(V.is_null(v))):
        return True, None
    for tag, val in (("nan", math.nan), ("pinf", math.inf), ("ninf", -math.inf)):
        if z3.is_true(model.eval(getattr(V, f"is_{tag}")(v))):
            return True, val
    if z3.is_true(model.eval(V.is_b(v))):
        return True, z3.is_true(model.eval(V.bv(v)))
    if z3.is_true(model.eval(V.is_i(v))):
        n = model.eval(V.iv(v)).as_long()
        if f is not None and f.type.base == "float":
            return True, float(n)
        if f is not None and f.type.base == "decimal":
            return True, decimal.Decimal(n)
        return True, n
    if z3.is_true(model.eval(V.is_r(v))):
        r = model.eval(V.rv(v))
        q = Fraction(r.numerator_as_long(), r.denominator_as_long())
        if f is not None and f.type.base == "decimal":
            return True, decimal.Decimal(q.numerator) / decimal.Decimal(q.denominator)
        return True, float(q)
    text = model.eval(V.sv(v)).as_string()
    return True, re.sub(r"\\u\{([0-9a-fA-F]+)\}", lambda m: chr(int(m.group(1), 16)), text)


def _admits(language: Any, values: dict[str, Any]) -> bool:
    """Whether the record built from `values` is a member, the language's
    own validation deciding; a record its class refuses to build is not."""
    names = {f.name for f in language.schema.fields}
    mapping = _SUPPORTED.get(language.ecosystem.name, True)
    given = values if mapping or language.schema.column_policy == "exact" \
        else {k: v for k, v in values.items() if k in names}
    try:
        row = language.ecosystem.build_row(language.schema, dict(given))
    except Exception:
        return False
    return bool(language.contains(row))


def _float_line(older: Any, newer: Any, base: dict[str, Any] | None) -> tuple[list[str], dict[str, Any] | None]:
    """Each float bound's neighbouring doubles run through both
    validations, on a member of `older`; the first one `older` admits and
    `newer` refuses, if any."""
    tried: list[str] = []
    if base is None:
        return tried, None
    fields = {f.name: f for f in older.schema.fields}
    for f in [*older.schema.fields, *newer.schema.fields]:
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
    """Whether `newer` admits every record `older` admits, read field by
    field: `proven`, `falsified` with a record `older` admits and `newer`
    refuses (built and confirmed by both validations), or `unknown` with
    the reason. `older` and `newer` are record languages, or anything
    `L[...]` resolves (a model class, a JSON Schema dict)."""
    z3 = _z3()
    from .schema.adaptors import adapt_row
    older, newer = (x if hasattr(x, "ecosystem") else adapt_row(x) for x in (older, newer))
    for language in (older, newer):
        why = untranslated(language)
        if why:
            return _InclusionResult("unknown", f"not translated: {why}")
    enc = MembershipEncoding(z3)
    names = list(dict.fromkeys([f.name for f in older.schema.fields]
                               + [f.name for f in newer.schema.fields]))
    try:
        m_older = enc.row(older.schema, names, "older", _SUPPORTED[older.ecosystem.name])
        m_newer = enc.row(newer.schema, names, "newer", _SUPPORTED[newer.ecosystem.name])
    except Untranslated as e:
        return _InclusionResult("unknown", f"not translated: {e}")
    solver = z3.Solver()
    solver.set("timeout", timeout_ms)
    solver.add(m_older, z3.Not(m_newer))
    # a witness reads best with the keys `older` does not declare left out,
    # so those are tried absent first and allowed only if they must be
    own = {f.name for f in older.schema.fields}
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
    fields = {f.name: f for f in [*newer.schema.fields, *older.schema.fields]}
    older_fields = {f.name: f for f in older.schema.fields}
    values: dict[str, Any] = {}
    for name in names:
        present, value = _value(enc, model, enc.var(name), older_fields.get(name, fields.get(name)))
        if present:
            values[name] = value
    if _admits(older, values) and not _admits(newer, values):
        return _InclusionResult("falsified", f"{older.name} admits it and {newer.name} refuses it",
                               values)
    return _InclusionResult("unknown", f"z3 offered {values!r}, which the validations do not "
                           f"confirm ({older.name} must admit it and {newer.name} refuse it); "
                           "this is a gap in the encoding")


def _a_member(language: Any) -> dict[str, Any] | None:
    import random
    try:
        row = language.sample(random.Random(0))
    except Exception:
        return None
    out = {}
    for f in language.schema.fields:
        if isinstance(row, dict):
            if f.name in row:
                out[f.name] = row[f.name]
        elif hasattr(row, f.name):
            out[f.name] = getattr(row, f.name)
    return out


__all__ = ["MembershipEncoding", "Untranslated", "untranslated"]
