# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The z3 seam a prover uses, driven through its public names alone, as
mathema's z3 rung would drive it: a claim's negation is asked of z3
over one encoding; no model is a proof; a model is decoded, built into
a record and confirmed by the language's own membership before it is
reported. Inclusion between two command-line versions, a bound on a
field over every command line, and a path field held to a root are
each proven or falsified this way."""
import argparse
from pathlib import Path

import pytest

z3 = pytest.importorskip("z3")

from mathema_language import smt  # noqa: E402
from mathema_language.schema.adaptors.cli_argparse import adapt  # noqa: E402
from mathema_language.text.path_language import path_within  # noqa: E402


def decide(negation, enc, language, names, confirm):
    """What a prover reports: 'proven', or the confirmed counterexample,
    or 'unknown'."""
    solver = z3.Solver()
    solver.set("timeout", 5000)
    solver.add(negation)
    answer = solver.check()
    if answer == z3.unsat:
        return "proven", None
    if answer != z3.sat:
        return "unknown", None
    candidate = enc.decode(solver.model(), language, names)
    return ("falsified", candidate) if confirm(candidate) else ("unknown", candidate)


def tool(retries=None, mode=("fast", "safe"), to=Path) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tool")
    p.add_argument("--retries", type=int, default=1, **({"choices": retries} if retries else {}))
    p.add_argument("--mode", choices=list(mode), default="safe")
    p.add_argument("--to", type=to, default=to("out"))
    return p


def test_the_surface_is_these_names():
    assert set(smt.__all__) == {"MembershipEncoding", "Untranslated", "build", "field_names",
                                "new_encoding", "untranslated"}


@pytest.mark.parametrize("newer_mode, verdict", [(("fast", "safe", "slow"), "proven"),
                                                 (("safe",), "falsified")])
def test_inclusion_of_one_version_in_another(newer_mode, verdict):
    older, newer = adapt(tool()), adapt(tool(mode=newer_mode))
    assert smt.untranslated(older) is None and smt.untranslated(newer) is None
    names = list(dict.fromkeys([*smt.field_names(older), *smt.field_names(newer)]))
    enc = smt.new_encoding(z3)
    negation = z3.And(enc.language(older, names, "older"), z3.Not(enc.language(newer, names, "newer")))

    def confirm(candidate):
        return older.contains(smt.build(older, candidate)) \
            and not newer.contains(smt.build(newer, candidate))
    got, witness = decide(negation, enc, older, names, confirm)
    assert got == verdict
    if verdict == "falsified":
        assert witness["mode"] == "fast"


@pytest.mark.parametrize("retries, verdict", [([1, 2, 3], "proven"), (None, "falsified")])
def test_a_bound_on_a_field_over_every_member(retries, verdict):
    language = adapt(tool(retries=retries))
    names = smt.field_names(language)
    enc = smt.new_encoding(z3)
    is_number, value = enc.number("retries")
    # the claim: every command line has retries <= 5; its negation, over members
    negation = z3.And(enc.language(language, names, "older"), enc.present("retries"),
                      is_number, value > 5)

    def confirm(candidate):
        return language.contains(smt.build(language, candidate)) and candidate["retries"] > 5
    got, witness = decide(negation, enc, language, names, confirm)
    assert got == verdict


def test_a_path_field_held_to_a_root():
    language, root = adapt(tool()), path_within("/ws")
    names = smt.field_names(language)
    enc = smt.new_encoding(z3)
    is_text, text = enc.string("to")
    negation = z3.And(enc.language(language, names, "older"), is_text,
                      z3.Not(enc.text(root, text, "newer")))

    def confirm(candidate):
        record = smt.build(language, candidate)
        return language.contains(record) and not root.contains(str(record.to))
    got, witness = decide(negation, enc, language, names, confirm)
    assert got == "falsified"


def test_what_the_encoding_does_not_read_is_named_before_any_z3_work():
    p = argparse.ArgumentParser(prog="t")
    p.add_argument("--when", type=lambda s: s.upper())
    assert "the type" in smt.untranslated(adapt(p))
