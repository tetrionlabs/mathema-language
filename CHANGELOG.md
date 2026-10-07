# Changelog

Notable changes to mathema-language are recorded here from its first
release onward.

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
