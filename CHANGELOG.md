# Changelog

Notable changes to mathema-language are recorded here from its first
release onward.

## Unreleased

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
- `L[yaml]` is the texts that are one YAML document, read as YAML 1.2
  by ruamel.yaml (the new `[yaml]` extra). Its first hazards are the
  documents a YAML 1.1 reader such as PyYAML reads differently
  (`country: no`, `on: push`, `mode: 012`, `t: 1:20`), and the texts no
  YAML reader accepts (a tab in the indentation, a key given twice) are
  outside it. `mathema_language.text.yaml_language.load` is the YAML 1.2
  reading, for comparing a loader against.
- `L[toml]` is the texts that are one TOML 1.0 document, read by
  `tomllib` (`tomli` before Python 3.11, the new `[toml]` extra). Its
  first hazards are the documents code most often mishandles once read:
  dates and times, which come back as `datetime` objects; `inf` and
  `nan`; an integer past 64 bits; dotted keys against a quoted key
  containing a dot; `version = 3.10`. The texts no TOML reader accepts
  (a key given twice, a leading zero, a trailing comma in an inline
  table) are outside it. `mathema_language.text.toml_language.load` is
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
