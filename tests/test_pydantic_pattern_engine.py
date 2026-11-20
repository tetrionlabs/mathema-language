# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A pydantic `Field(pattern=...)` is validated by the rust regex engine
unless the model sets `regex_engine='python-re'`, and the encoding reads
patterns as Python's `re`. pydantic itself is the referee here: a
pattern the encoding reads for a rust-validated field must bracket what
the model admits, and a construct the two engines read differently, or
are not shown to read alike, is refused by name."""
import random

import pytest

pydantic = pytest.importorskip("pydantic")

from mathema_language import smt  # noqa: E402
from mathema_language.schema.adaptors import adapt_row  # noqa: E402
from mathema_language.text import _regular as rx  # noqa: E402

#: whether the installed pydantic knows `regex_engine` (2.5 and later)
KNOWS_ENGINE = tuple(int(part) for part in pydantic.VERSION.split(".")[:2]) >= (2, 5)


def model(pattern, engine=None):
    """A model with one field held to `pattern`, or None when the installed
    pydantic refuses to build it (its engine rejects the pattern outright)."""
    config = pydantic.ConfigDict(regex_engine=engine) if engine else pydantic.ConfigDict()
    try:
        class M(pydantic.BaseModel):
            model_config = config
            s: str = pydantic.Field(pattern=pattern)
    except Exception as e:  # noqa: BLE001 -- pydantic-core's SchemaError, by any of its names
        assert "regex" in str(e).lower() or "pattern" in str(e).lower(), e
        return None
    return M


def unread_metadata(why):
    """Whether the encoding refuses the model before it reaches the pattern: an
    early pydantic 2 keeps a field's settings under a name the encoding does not read."""
    return why is not None and "PydanticGeneralMetadata" in why


def admits(M, text):
    try:
        M(s=text)
    except pydantic.ValidationError:
        return False
    return True


SHARED = [r"^[A-Z]{3}-[0-9]{4}$", r"a", r"^a$", r"a$", r"^ab|cd", r"a.c", r"[^a]b", r"(?:ab)+c",
          r"a{2,3}", r"a*?b", r"x(a|b)?y", r"\Aab", r"[a-c0-2]+", r"\.\*", r"\x41é",
          r"a\tb", r"(?P<n>a)b", r"^$", r"[^\n]x", r"\-\/", "\\u00e9x", "a\\U0001F600"]
ALPHABET = list("abcxyABC012-./*") + ["\n", "\t", "é", " ", "٣", "\U0001F600"]


def texts(n=300, seed=7):
    rng = random.Random(seed)
    out = {"", "\n", "a", "a\n", "ABC-1234", "ABC-1234\n", "xABC-1234", "Aé", "ab", "cd", ".*", "-/"}
    while len(out) < n:
        out.add("".join(rng.choice(ALPHABET) for _ in range(rng.randint(1, 6))))
    return sorted(out)


@pytest.mark.parametrize("pattern", SHARED)
def test_a_shared_construct_brackets_what_the_rust_engine_admits(pattern):
    M = model(pattern)
    if M is None:
        pytest.skip(f"pydantic {pydantic.VERSION} refuses to build a model with this pattern")
    why = smt.untranslated(adapt_row(M))
    if unread_metadata(why):
        pytest.skip(f"pydantic {pydantic.VERSION}: the encoding does not read this pydantic's field settings")
    assert why is None
    at_least, at_most = rx.term(pattern, 0, "contains"), rx.term(pattern, 0, "matches")
    assert at_least["exact"] and at_most["exact"]
    for text in texts():
        admitted = admits(M, text)
        assert not admitted or rx.member(at_least, text), (pattern, text)
        assert not rx.member(at_most, text) or admitted, (pattern, text)


# a refused construct, and a string the two engines part on where one is known
REFUSED = [(r"\s", "\x1c"), (r"\S", "\x1c"), (r"\w", "²"), (r"\W", "́"),
           (r"a\b", "a²"), (r"\B", "²"), (r"[a&&b]", "&"), (r"[a~~b]", "~"),
           (r"[[a]]", "a"), (r"[+--]", ","), (r"\<", "<"), (r"a*+a", "aa"),
           (r"\d", None), (r"\D", None), (r"[\d]", None), (r"(?i)k", None), (r"(?s).", None),
           (r"(?m)^a", None), (r"(?i:a)", None), (r"(?x) a", None), (r"[]a]", None)]


@pytest.mark.filterwarnings("ignore::FutureWarning")
@pytest.mark.parametrize("pattern, parts_at", REFUSED)
def test_a_construct_the_engines_are_not_shown_to_share_is_refused(pattern, parts_at):
    import re
    M = model(pattern)
    if M is None:
        # the installed engine refuses at build a pattern `re` compiles: the two part there
        assert re.compile(pattern) and smt._rust_reads_differently(pattern)
        return
    why = smt.untranslated(adapt_row(M))
    assert why is not None
    if not unread_metadata(why):
        assert "rust regex engine" in why and repr(pattern) in why
    if parts_at is not None:
        assert admits(M, parts_at) != bool(re.search(pattern, parts_at))


@pytest.mark.filterwarnings("ignore::FutureWarning")
@pytest.mark.parametrize("pattern", [p for p, _ in REFUSED])
def test_an_inclusion_over_a_refused_construct_is_unknown(pattern):
    pytest.importorskip("z3")
    M = model(pattern)
    if M is None:
        pytest.skip(f"pydantic {pydantic.VERSION} refuses to build a model with this pattern")
    result = smt._schema_inclusion(M, M)
    assert result.verdict == "unknown"
    assert "rust regex engine" in result.reason or unread_metadata(result.reason)


@pytest.mark.skipif(not KNOWS_ENGINE, reason="regex_engine arrived in pydantic 2.5")
@pytest.mark.filterwarnings("ignore::FutureWarning")
@pytest.mark.parametrize("pattern", [r"\s", r"\w+", r"(?i)k", r"a\b", r"[\d]"])
def test_a_model_on_the_python_engine_is_read(pattern):
    import re
    M = model(pattern, "python-re")
    assert smt.untranslated(adapt_row(M)) is None
    for text in ["\x1c", "\u00b2", "\u212a", "a", "a\u00b2", "1", ""]:
        assert admits(M, text) == bool(re.search(pattern, text))


def test_the_setting_counts_only_where_pydantic_knows_it(monkeypatch):
    class M(pydantic.BaseModel):
        model_config = pydantic.ConfigDict(regex_engine="python-re") if KNOWS_ENGINE else {
            "regex_engine": "python-re"}
        s: str = pydantic.Field(pattern="a")

    assert smt._reads_patterns_with_re(M) is KNOWS_ENGINE
    monkeypatch.setattr(pydantic, "VERSION", "2.4.2")
    assert smt._reads_patterns_with_re(M) is False
    monkeypatch.setattr(pydantic, "VERSION", "2.5.0")
    assert smt._reads_patterns_with_re(M) is True


def test_the_review_pair_is_no_longer_proven():
    pytest.importorskip("z3")
    older, newer = model(r"^\x1c"), model(r"^\s(.|\n)*$")
    if older is None or newer is None:
        pytest.skip(f"pydantic {pydantic.VERSION} refuses to build a model with these patterns")
    result = smt._schema_inclusion(older, newer)
    assert result.verdict == "unknown" and r"\\s" in result.reason
    assert admits(older, "\x1c") and not admits(newer, "\x1c")


def test_a_pattern_in_a_nested_model_is_held_to_the_same_rule():
    class Inner(pydantic.BaseModel):
        s: str = pydantic.Field(pattern=r"\s")

    class Outer(pydantic.BaseModel):
        model_config = pydantic.ConfigDict(regex_engine="python-re") if KNOWS_ENGINE else {}
        inner: Inner

    why = smt.untranslated(adapt_row(Outer))
    assert why is not None and (".inner.s" in why or unread_metadata(why))


def test_the_table_of_constructs_is_what_these_tests_show():
    import json
    from pathlib import Path
    table = json.loads((Path(__file__).parent / "data" / "python_rust_constructs.json").read_text())
    assert {d["pattern"] for d in table["different"]} == {p for p, parts in REFUSED if parts}
    assert {d["pattern"] for d in table["not_shown_identical"]} <= {p for p, parts in REFUSED if not parts}
    assert {e for d in table["identical"] for e in d["examples"]} <= set(SHARED)
    assert pydantic.VERSION.split(".")[0] in {v.split(".")[0] for v in table["measured_against"]["pydantic"]}
    for d in table["different"]:
        import re
        M = model(d["pattern"])
        if M is not None:
            assert admits(M, d["parts_at"]) != bool(re.search(d["pattern"], d["parts_at"]))
