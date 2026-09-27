# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The neutral schema model: the types, constraints, fields, keys and
row-count bounds every ecosystem's schema is read into, so that one
generator, one checker and one explain grammar serve them all.
Everything here is a frozen dataclass; `None` is null in a neutral
record and NaN is a distinct float value."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

#: the base types a `NeutralType` can have
BASES = ("bool", "int", "float", "decimal", "string", "binary", "date", "time",
         "datetime", "duration", "categorical", "list", "struct", "map", "ref", "any")

#: the draw bounds a recursive schema is sampled within when it states
#: none of its own; they are sampling choices, published by the
#: language, never a bound on its members
SAMPLING_BOUNDS = {"depth": 8, "nodes": 256, "children": 16}

#: the marker for a field with no default and a constraint with no constant
NO_DEFAULT: Any = type("NoDefault", (), {"__repr__": lambda self: "NO_DEFAULT"})()


@dataclass(frozen=True)
class NeutralType:
    """One type: `base` from `BASES`, with `bits` and `signed` for a
    fixed-width number, `precision` and `scale` for a decimal, `unit`
    and `tz` for a datetime or duration (`tz` None means naive),
    `levels` and `ordered` for a categorical, `item` for a list,
    `fields` for a struct, `key` and `value` for a map, and for a
    `ref` the name of a record type among the schema's definitions,
    which is how a schema refers to itself. `construct` builds a
    struct's value from its field values (a dataclass or model class);
    without it a struct's value is a dict."""
    base: str
    bits: int | None = None
    signed: bool = True
    precision: int | None = None
    scale: int | None = None
    unit: str | None = None
    tz: str | None = None
    levels: tuple[Any, ...] | None = None
    ordered: bool = False
    item: NeutralType | None = None
    fields: tuple[Field, ...] | None = None
    key: NeutralType | None = None
    value: NeutralType | None = None
    ref: str | None = None
    construct: Callable[..., Any] | None = field(default=None, compare=False, repr=False)

    def __post_init__(self) -> None:
        if self.base not in BASES:
            raise ValueError(f"unknown base type {self.base!r}; one of {BASES}")

    @property
    def numeric(self) -> bool:
        return self.base in ("int", "float", "decimal")

    def render(self) -> str:
        """The type as text: `int64`, `string`, `categorical[a, b]`,
        `list[int]`, `datetime[ns, UTC]`."""
        if self.base in ("int", "float") and self.bits:
            return f"{'u' if self.base == 'int' and not self.signed else ''}{self.base}{self.bits}"
        if self.base == "decimal" and self.precision is not None:
            return f"decimal({self.precision}, {self.scale or 0})"
        if self.base in ("datetime", "duration") and (self.unit or self.tz):
            inside = ", ".join(x for x in (self.unit, self.tz) if x)
            return f"{self.base}[{inside}]"
        if self.base == "categorical" and self.levels is not None:
            return f"categorical[{', '.join(str(level) for level in self.levels)}]"
        if self.base == "list" and self.item is not None:
            return f"list[{self.item.render()}]"
        if self.base == "struct" and self.fields is not None:
            return "struct{" + ", ".join(f"{f.name}: {f.type.render()}" for f in self.fields) + "}"
        if self.base == "ref" and self.ref is not None:
            return self.ref
        if self.base == "map" and self.key is not None and self.value is not None:
            return f"map[{self.key.render()}, {self.value.render()}]"
        return self.base


@dataclass(frozen=True)
class Constraints:
    """The value constraints a field carries beyond its type: bounds
    (inclusive `min`/`max`, or the exclusive pair), a length range for
    text, binary and lists, a regular expression the whole text must
    match, an enumeration, a constant, and a divisor."""
    min: Any = None
    max: Any = None
    exclusive_min: Any = None
    exclusive_max: Any = None
    min_len: int | None = None
    max_len: int | None = None
    regex: str | None = None
    enum: tuple[Any, ...] | None = None
    const: Any = NO_DEFAULT
    multiple_of: Any = None

    def __bool__(self) -> bool:
        return any(v is not None for v in (self.min, self.max, self.exclusive_min,
                                           self.exclusive_max, self.min_len, self.max_len,
                                           self.regex, self.enum, self.multiple_of)) \
            or self.const is not NO_DEFAULT

    @property
    def low(self) -> Any:
        """The lower bound, whichever kind is set."""
        return self.min if self.min is not None else self.exclusive_min

    @property
    def high(self) -> Any:
        """The upper bound, whichever kind is set."""
        return self.max if self.max is not None else self.exclusive_max

    def render(self) -> str:
        parts: list[str] = []
        if self.low is not None or self.high is not None:
            lo = "(" if self.min is None else "["
            hi = ")" if self.max is None else "]"
            parts.append(f"{lo}{'-inf' if self.low is None else self.low}, "
                         f"{'inf' if self.high is None else self.high}{hi}")
        if self.min_len is not None or self.max_len is not None:
            parts.append(f"len in [{self.min_len or 0}, {self.max_len if self.max_len is not None else 'inf'}]")
        if self.regex is not None:
            parts.append(f"matches {self.regex!r}")
        if self.enum is not None:
            parts.append("one of {" + ", ".join(repr(v) for v in self.enum) + "}")
        if self.const is not NO_DEFAULT:
            parts.append(f"== {self.const!r}")
        if self.multiple_of is not None:
            parts.append(f"multiple of {self.multiple_of}")
        return ", ".join(parts)


@dataclass(frozen=True)
class Field:
    """One column or attribute: its type, whether null is a member
    (`nullable`) and whether the column may be absent from a mapping
    row (`required`), whether its values are unique across a table,
    its constraints, whether NaN is a member of a float field, its
    default, and free metadata as pairs."""
    name: str
    type: NeutralType
    nullable: bool = False
    required: bool = True
    unique: bool = False
    constraints: Constraints = field(default_factory=Constraints)
    nan_allowed: bool = False
    default: Any = NO_DEFAULT
    metadata: tuple[tuple[str, Any], ...] = ()

    def render(self) -> str:
        text = f"{self.name}: {self.type.render()}"
        if self.nullable:
            text += " | null"
        if self.constraints:
            text += f" ({self.constraints.render()})"
        return text


@dataclass(frozen=True)
class RowSchema:
    """One record type: its fields in order, whether a row may carry
    columns the schema does not name (`column_policy` `"exact"` or
    `"open"`), and opaque row checks, each a predicate over the whole
    row that membership requires and generation satisfies by
    rejection. `definitions` names every record type a `ref` field may
    point at, the schema itself included when it refers to itself."""
    name: str
    fields: tuple[Field, ...]
    column_policy: str = "exact"
    checks: tuple[Callable[[Any], bool], ...] = ()
    definitions: tuple[tuple[str, RowSchema], ...] = ()
    construct: Callable[..., Any] | None = field(default=None, compare=False, repr=False)

    def definition(self, name: str) -> RowSchema:
        """The record type a `ref` names."""
        if name == self.name:
            return self
        for key, schema in self.definitions:
            if key == name:
                return schema
        raise KeyError(name)

    @property
    def recursive(self) -> bool:
        """Whether any field reaches a `ref`, at any depth."""
        stack = [f.type for f in self.fields]
        stack += [f.type for _, d in self.definitions for f in d.fields]
        while stack:
            t = stack.pop()
            if t.base == "ref":
                return True
            stack += [x for x in (t.item, t.key, t.value) if x is not None]
            stack += [f.type for f in (t.fields or ())]
        return False

    def __post_init__(self) -> None:
        if self.column_policy not in ("exact", "open"):
            raise ValueError(f"column_policy must be 'exact' or 'open', not {self.column_policy!r}")
        names = [f.name for f in self.fields]
        if len(set(names)) != len(names):
            raise ValueError(f"duplicate field names in {self.name}: {names}")

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields)

    def field(self, name: str) -> Field:
        for f in self.fields:
            if f.name == name:
                return f
        raise KeyError(name)

    def render(self) -> str:
        return f"{self.name}{{" + ", ".join(f.render() for f in self.fields) + "}"


@dataclass(frozen=True)
class ForeignKey:
    """Columns of this table that must appear as `parent_columns` of
    the table named `parent`."""
    columns: tuple[str, ...]
    parent: str
    parent_columns: tuple[str, ...]


@dataclass(frozen=True)
class TableSchema:
    """A table of `row`: its primary key and other unique column sets,
    foreign keys, the closed row-count range (`None` for no upper
    bound), opaque table checks, and the columns the rows are sorted
    by."""
    row: RowSchema
    primary_key: tuple[str, ...] = ()
    unique: tuple[tuple[str, ...], ...] = ()
    foreign_keys: tuple[ForeignKey, ...] = ()
    row_count: tuple[int, int | None] = (0, None)
    checks: tuple[Callable[[Any], bool], ...] = ()
    ordered: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        lo, hi = self.row_count
        if lo < 0 or (hi is not None and hi < lo):
            raise ValueError(f"row_count must be a closed range from 0, not {self.row_count}")
        for cols in (self.primary_key, *self.unique, self.ordered,
                     *(fk.columns for fk in self.foreign_keys)):
            for col in cols:
                if col not in self.row.names:
                    raise ValueError(f"{self.row.name} has no column {col!r}")

    @property
    def name(self) -> str:
        return self.row.name

    @property
    def key_sets(self) -> tuple[tuple[str, ...], ...]:
        """The primary key first, then every other unique set."""
        return ((self.primary_key,) if self.primary_key else ()) + self.unique


__all__ = ["BASES", "NO_DEFAULT", "Constraints", "Field", "NeutralType", "RowSchema"]
