# Changelog

Notable changes to mathema-language are recorded here from its first
release onward.

## 0.4.1

For mathema 0.6.6.2 (`mathema>=0.6.6.2,<0.7`), which reads a language's persisted `term`.

- Fixed: an inclusion between two record languages was reported proven when the older one admits
  a key the newer one does not declare and refuses. A JSON Schema object that allows other keys was
  proven included in the same object with `additionalProperties: false`, and in a plain class or a
  total `TypedDict` with the same fields; a pydantic model with `extra="ignore"` was proven included
  in one with `extra="forbid"`. Each is now falsified with a record both sides' validation confirm
  (`{"a": "x", "other_0": 0}`, for example). From 0.2.1.
- Fixed: five record constructs the encoding does not read gave proven inclusions their validators
  contradict; each now leaves the inclusion unknown, naming the construct: a nested pydantic model
  with its own `extra` setting; `additionalProperties` holding a schema for the keys no property
  names; a `required` key no property names; a pydantic model in its default lax mode, with a field
  that is not text, compared with another library's schema (pydantic accepts `"1"` for an `int`);
  and a pydantic field read by an alias. A pydantic model with `ConfigDict(strict=True)` is read as
  before. From 0.2.1.
- Fixed: from 0.4.0, `mathema_language.text.pattern_language` with a
  `version` other than the running Python, or with none (every
  supported Python), read the pattern with the running interpreter's
  `re`, so where versions differ in what a pattern accepts (`\N{...}`
  names, loosely written conditional group references, and other
  constructs in the delta table) the language for the pinned version
  could be wrong and a claim over it reported proven. A pinned version
  is now read as that version reads it, or refused.
- Upgrade note: a path language confined to one root renders
  `L[path, within ("/root")]`, the word followed by its arguments in
  brackets, where it rendered `L[path, within "/root"]`. Text that was
  stored or compared in the old spelling changes; the old spelling is
  still read (`within_arguments` reads both to the same arguments).
- `mathema_language.text.pattern_language` is now
  `mathema_language.text.regex_language`. The old name still works in
  0.4.x, with a `DeprecationWarning`, and goes in 0.5.0.
- A pydantic record built to check membership keeps the keys its model does not declare, so a model
  with `extra="forbid"` refuses them as its validator does.
- When a library a language or adaptor reads with is not installed, the error names it and the extra
  that installs it: `L[yaml] is read with ruamel.yaml, which is not installed; install
  mathema-language[yaml]`. The same holds for `L[toml]` before Python 3.11 (tomli), an inclusion
  (z3, the `smt` extra) and a JSON Schema (jsonschema). The error is a `MissingLibrary`, an
  `ImportError`.
- Text words for `L[...]`, registered with mathema's word registry: `matches (P)`, `contains (P)`,
  `starts with (P)` (also `^=`) and `ends with (P)` (also `$=`), where `P` is a quoted text, a
  `re(r"...", python[, flags])` call or a `pattern ("...")`; `pattern ("AA99[ ]9AA")`, a picture of
  fixed-format text; `within (...)` over paths, IPv4 and IPv6 blocks, ISO dates and datetimes; and
  the alphabet constructor `L[lower + digit + "_"]`, with the languages `L[lower]`, `L[upper]` and
  the alphabet `hexdigit`. `re(...)` takes a version pin (`python 3.13`), read from the table of
  where Python versions differ. The word `within` is draft and has no lexicon row yet.
- Known issue: on macOS, the README claim over `L[json]` that a configuration normalises twice to
  the same text can be reported holds where it is falsified, since the probe may not draw a document
  nested past the recursion limit.

## 0.4.0

For mathema 0.6.6.1 (`mathema>=0.6.6.1,<0.7`).

- Fixed: an inclusion between two record languages could be reported
  proven when it does not hold over a decimal field the encoding read
  otherwise than its validation. From 0.2.1: a decimal with a precision
  and no scale (decimal(3) was proven inside decimal(2), though 123 is
  in the one and not the other), and a pydantic decimal that admits NaN
  and the infinities (under pydantic releases before 2.14). From 0.3.0:
  a decimal with a scale and no precision (decimal(scale=2) between -1
  and 1 was proven inside decimal(3, 2), though 0.001 is in the one and
  not the other), and in pydantic models a decimal with one of its two
  digit limits inside a nested model, a custom validator on a nested
  model, and a decimal whose digits are all places (pydantic refuses a
  number written with no point there, zero included). The pydantic
  decimal whose digits are all places is now read as pydantic validates
  it; each of the other cases is declined by name, wherever the field
  stands, and the inclusion is unknown with the reason.
- Fixed: from 0.3.0, an inclusion between two record languages (two JSON
  Schemas, for example) could be reported proven when it does not hold
  if a field's name held a dot. Such a field was read as the same field
  as one of a nested record spelled the same way (a field named `"a.b"`
  and field `b` of a record `a`), and a closed record that declares no
  field of that name did not refuse it. Every field is now read as its
  own, whatever its name holds.
- For callers of the record encoding: a field is now named one way, its
  field names from the top record down, each with its backslashes and
  dots preceded by a backslash, joined by dots. `field_names` gives
  these names, and `MembershipEncoding` (`var`, `row`, `language`,
  `present`, `number`, `string`) and `build` read them. A plain name is
  unchanged: `x`, and `x.qty` for field `qty` of record `x`. A field of
  the top record named `a.b` is now `a\.b`. A dotted name a caller
  passes is read as a nested field, so a caller should pass the names
  `field_names` gives. `MembershipEncoding.vars` is keyed by field paths
  (tuples of names), and the labels of the z3 variables changed.
- An inclusion between two JSON Schema record languages whose string
  fields carry patterns ending in `$` is decided; it came back unknown.
  Inside a JSON Schema record a pattern is read the way the `jsonschema`
  validator reads it, by `re.search`, on both sides of the inclusion.
- A Python `re` pattern is translated exactly by the z3 encoding or
  refused by name: anchors (`^`, `$`, `\A`, `\Z`, `\b`, `\B`), flags,
  classes and repeats are read as `re` reads them, and a construct the
  encoding does not read (a possessive repeat, a back-reference, a
  look-around) gives `unknown` with the reason where it could give a
  wrong answer before.
- `mathema_language.text.pattern_language(source)` is the text language
  of a compiled pattern, a pattern text, or a bound `PAT.fullmatch`,
  `PAT.search` or `PAT.match`.
- A text language states what it is as a regular-language term under
  `term` in its persisted form (`to_json`): the alphabet
  languages, `L[path]`, and the format languages `L[slug]`, `L[hex]`,
  `L[base64]`, `L[ipv4]`, `L[ipv6]` and `L[shell_safe]` exactly;
  `L[identifier]`, `L[uuid]`, `L[iso_date]` and `L[iso_datetime]` as a
  pair of bounds that hold on every supported Python. `L[json]`,
  `L[yaml]` and `L[toml]` are not regular and say so under
  `no_term`. A length bound on a language with a term states the
  bounded term.
- A regular-language term whose document is malformed (a version or an
  exact flag of the wrong type, a flag that contradicts the keys
  present, a missing key) is refused with `ValueError`, and a text with
  a character outside a term's alphabet is not a member of it.

## 0.3.0

For mathema 0.6.6.1 (`mathema>=0.6.6.1,<0.7`).

- The z3 membership encoding reads command lines: an argparse parser's
  namespace language, each subcommand a shape of its own, with flags,
  choices, typed values, `pathlib.Path` arguments as their text, and
  options taking several values (`nargs`, `append`) as sequences. A
  `type=` the encoding does not read is named.
- A positional argument taking several values (`nargs="+"`, `"*"` or a
  count) is never `None` in the argparse namespace language, as
  argparse never gives it one; it was read as nullable.
- `L[path]` is path text, and
  `mathema_language.text.path_language.path_within(root)` the paths
  confined to a root (no `..` segment; an absolute path only at or under
  the root), rendered `L[path, within "/root"]`. Both are defined by a
  regular expression the z3 encoding reads exactly. Their hazards are
  the paths code reads wrongly: a doubled or trailing slash, a leading
  `./`, a newline or leading space in a name, names outside ASCII, and a
  name longer than most filesystems allow. None names a real place or
  climbs out of the directory it starts in.
- `mathema_language.openapi.operation(spec, operation_id)` reads an
  OpenAPI 3 operation as the language of the requests it accepts: a
  record of its path, query, header and cookie parameters and its JSON
  body, written as one JSON Schema (`request_schema`), with what its
  HTTP method says about it (`read_only`, `idempotent`, `destructive`).
- The z3 encoding reads nested records (each field a variable under its
  dotted name), and treats only the JSON Schema keywords `jsonschema`
  enforces and the adaptor does not read as unread: `format`, which the
  validator does not check, no longer stops it.
- `mathema_language.smt` states its surface for a prover: `untranslated`,
  `field_names`, `new_encoding` (an encoding whose `language` and
  `text` give membership formulas, `number`, `string` and `present` the
  terms a relation over a field is written in, and `decode` a model as
  the value it describes) and `build`, the record a candidate makes, for
  confirming it with the language's own membership.
- A claim names an OpenAPI operation by the dotted path of a module
  attribute holding one (`L[app.api.create_order]`).

## 0.2.1

For mathema 0.6.2 (`mathema>=0.6.2,<0.7`).

- A field of a referenced record type checked with no definitions to
  resolve the reference is a problem; it accepted every value before.
- `mathema_language.schema.emptiness.not_empty(field)` says whether a
  field describes any value at all, decided by constructing candidate
  members from its bounds, lengths, levels, divisor and regular
  expression and checking each with the field's own checker. A claim
  over schema fields can take it as a premise:
  `assuming not_empty(f) == True`.
- The simplest member of a field with no members is `None`, where it
  was a value the field refuses; a bound its type cannot read, or a
  regular expression that does not compile, no longer raises from the
  checker or the generator.
- `NeutralType` and `Constraints` refuse a width, precision, scale or
  length that cannot mean anything (a negative width, a scale above the
  precision), and say which.
- A pydantic, Django or JSON Schema record language declares that
  library's `ValidationError` as its refusal, so `excluded_outside_domain`
  over its records holds for a function that refuses an invalid record
  through the library's validation and is falsified for one that refuses
  with an error of its own; a dataclass, TypedDict or SQLAlchemy record
  declares none, and any raise refuses.
- The lexicon rows `path_index_present` and `path_index_missing` bound
  the first line's quantity as `in {7}` (and `in {7} | {absent}`), where
  they wrote the one-point interval `[7, 7]`; their verdicts are
  unchanged. The ten `structure_*` and eight `path_*` rows are frozen:
  their names and meanings no longer change.
- `mathema_language.smt` encodes a record language's membership as a z3
  formula (the new `[smt]` extra), reading at least or at most what the
  language's library admits, for a solver deciding whether one schema
  admits everything another does. It reads pydantic models, JSON Schema
  dicts, dataclasses and TypedDicts field by field, and names whatever
  it does not read.
- A pydantic decimal's `max_digits` and `decimal_places` are its
  precision and scale, so its record language draws members pydantic
  accepts; it drew none before.
- Text drawn for a pattern with a negated category (`\S`, `\D`, `\W`)
  matches it; it drew the category itself, so a record with a pattern
  such as `^\S+@\S+\.\w{2,}$` had no member to draw.

## 0.2.0

For mathema 0.6.2 (`mathema>=0.6.2,<0.7`).

- A claim over the namespaces of a command line with no subcommands,
  whose function reads only numeric options, is proven (the lexicon row
  `adaptor_argparse_proven`); a function that branches on a subcommand
  or an option with `choices` is decided by running the code, so a true
  claim there `holds`.
- The argv language declares how a program refuses and answers: a
  command line outside it is refused with `SystemExit` and exit code 2,
  as argparse refuses it, and one inside it is answered with a return or
  `SystemExit` with exit code 0 or 1, so `excluded_outside_domain` and
  `is_language_defined` over a command line check exactly that.
- A record class that refuses values in its constructor (a dataclass
  `__post_init__` that raises) is a language like any other: a value
  its class refuses is not a member, so drawing, hazards and the
  simplest member pass over it instead of raising out of the check.
- A record field annotated `Any` or `object` admits `None`, as the
  dataclass, TypedDict or pydantic model itself does.
- A Spark schema is a record language: a `pyspark.sql.types.StructType`,
  or the JSON Spark writes for one (`df.schema.jsonValue()`, a Delta
  log's `schemaString`), read without importing pyspark. Each Spark type
  has its neutral type, including the integer widths, `decimal(p, s)`,
  nullable fields, a CHAR or VARCHAR length, and arrays and maps whose
  items may be null.
- A `decimal(p, s)` field holds its precision and scale in every
  adaptor: a member has at most `s` places after the point and at most
  `p - s` digits before it, the hazards include the largest value it
  holds and its smallest step, and the values just outside are one step
  past the largest and one place too many.

- A command line is a record language: an `argparse.ArgumentParser`, or
  a function annotated to build one, is the language of the namespaces
  `parse_args` returns, one field per action as argparse applies it and
  one shape per subcommand, so a function taking `args` is claimed over
  every namespace a user can produce.
- A union of record languages, one branch per shape, which a parser with
  subcommands reads as.
- `mathema_language.spark.rule` reads a column a Spark function computes
  (a `withColumn` chain of `when`, comparisons, `isNull`, `isin`,
  `between`, `coalesce` and arithmetic) from the function's source,
  without pyspark, and returns it as a Python function of the columns it
  reads, with Spark's handling of null and NaN written in, so a banding
  rule is proven over every value and an edge written wrongly is found.
  Anything outside that subset is refused by name.
- `mathema_language.spark.holes` reports what a Spark rule writes at each
  hole of each column it reads (`null`, and `nan` for a floating-point
  column), and whether the code decided it (an `isNull`, `isnan` or
  `coalesce`), Spark's semantics decided it (a fall-through to
  `otherwise`, NaN compared as above every number, null through
  arithmetic), or it depends on another column. The rule reader also
  reads `isnan`.

- `mathema_language.argv.argv_language` is the language of the command
  lines an argparse parser accepts: drawn in every spelling argparse
  reads the same, with membership by the parser and refusals in its own
  words, and the hazards command lines break on (`--help` on every
  subcommand, a negative number, an empty value, a value starting with a
  dash, an abbreviation, a repeated option). A parser whose arguments
  open files is refused.
- Reading an argparse parser notes the defects argparse accepts when
  the parser is built: `type=bool`, a default outside its choices, a
  text default its type refuses, two options storing into one name,
  choices the type never produces, and help text that fails to format.
  Both argparse languages warn with each note (`ParserNoteWarning`), and
  `mathema_language.argv.parser_notes` returns them.
- `L[yaml]` is the texts that are one YAML document, read as YAML 1.2
  by ruamel.yaml (the new `[yaml]` extra). Its first hazards are the
  documents a YAML 1.1 reader such as PyYAML reads differently
  (`country: no`, `on: push`, `mode: 012`, `t: 1:20`), and the texts no
  YAML reader accepts (a tab in the indentation, a key given twice) are
  outside it. `mathema_language.text.yaml_language.load` is the YAML 1.2
  reading, for comparing a loader against.
- `L[toml]` is the texts that are one TOML document, read by `tomllib`
  (`tomli` before Python 3.11, the new `[toml]` extra), as TOML 1.0 or
  1.1 according to the reader (`TOML_VERSION`). Its first hazards are the documents code most often mishandles once read:
  dates and times, which come back as `datetime` objects; `inf` and
  `nan`; an integer past 64 bits; dotted keys against a quoted key
  containing a dot; `version = 3.10`; and, with a TOML 1.1 reader, the
  documents a 1.0 reader refuses. The texts no TOML reader accepts (a
  key given twice, a leading zero, a date that does not exist) are
  outside it. `mathema_language.text.toml_language.load` is
  its reading.

## 0.1.0

The first release, for mathema 0.6.1 (`mathema>=0.6.1,<0.7`).

- Text languages for `L[...]`: `unicode`, `printable`, `latin-1`,
  `ascii`, the ASCII `digit`, `alpha` and `alnum`, `unicode_alpha` and
  `unicode_alnum` for any script, and `identifier`. Each brings its own
  hazards, the inputs code most often gets wrong, which mathema tries
  before random members.
- Format languages defined by the parser Python already has: `json`,
  `uuid`, `iso_date`, `iso_datetime`, `ipv4`, `ipv6`, `base64`, `hex`,
  `slug` and `shell_safe`. `iso_date` and `iso_datetime` offer every
  spelling the running Python's parser reads, so a claim true only of
  the canonical spelling is falsified.
- The hazard alphabets `control`, `invisible`, `combining`, `surrogate`,
  `compatibility` and `astral`.
- Refinements inside the brackets: `len` for text, and `depth`, `nodes`
  and `width` for trees and JSON documents.
- Record languages from the schema a project already has: dataclasses,
  TypedDicts, pydantic models, JSON Schema, SQLAlchemy tables and Django
  models, each deciding membership with its own library's validation,
  plus `Annotated[str, ...]` text annotations.
- Paths into a record (`o.lines[*].qty`) and the absent and hole rule of
  mathema 0.6.1: a bound on a path means the value is there, and
  `| {absent}` keeps a record whose path reaches nothing.
- Structural induction over recursive record trees, so a fold over a
  tree bounded by `depth` is proven, not only tested.
- The built-in claims `is_encoding_safe` and `is_length_safe`.
- `refused_inputs` and `narrow_language`, to see what a function refuses
  and to quantify over what it accepts.
- A text vocabulary (`mathema_language.text`) and a tree vocabulary
  (`mathema_language.tree`) for use inside claims, bound with `let`.
- A lexicon of worked claims, checked by the test suite against its
  pinned verdicts.
- Documentation: a six-page tutorial, a how-to, and a reference for
  every language, refinement, adaptor and built-in claim, with every
  example run by the test suite.
