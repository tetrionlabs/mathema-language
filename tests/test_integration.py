# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Everything that needs a live mathema goes here: the entry points are
discovered, a name resolves from them, a claim over a language holds
with the dialect stamp and the record naming this package, an encoding
boundary falsifies with the member as witness, and an unknown name is
still refused."""
import textwrap
from importlib.metadata import entry_points

import pytest

pytest.importorskip("mathema")

import pathlib  # noqa: E402

try:
    import tomllib
except ImportError:                       # Python 3.10
    tomllib = pytest.importorskip("tomli")

from mathema.conjecture import check_conjectures, claim  # noqa: E402
from mathema.domain import LanguageRef  # noqa: E402
from mathema.languages import UnknownLanguage, resolve  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load(tmp_path, body, name="lang_pkg_fns"):
    import importlib.util
    p = tmp_path / f"{name}.py"
    p.write_text(textwrap.dedent(body))
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_entry_points_match_the_pyproject_table():
    declared = tomllib.loads((ROOT / "pyproject.toml").read_text())
    table = declared["project"]["entry-points"]["mathema.languages"]
    discovered = {ep.name: ep.value for ep in entry_points(group="mathema.languages")
                  if ep.value.startswith("mathema_language")}
    assert discovered == table


def test_a_name_resolves_from_the_entry_point():
    language, source = resolve(LanguageRef("ascii"))
    assert language.name == "ascii"
    assert source.startswith("entry point mathema_language")


def test_a_claim_over_a_language_holds_with_the_dialect_and_the_source(tmp_path):
    mod = _load(tmp_path, '''
        def shout(s: str) -> str:
            """Upper case."""
            return s.upper()
    ''')
    (p,) = check_conjectures(mod.shout, [claim("for s in L[ascii], len(f(s)) == len(s)")])
    assert p.verdict == "holds", (p.verdict, p.note, p.counterexample)
    assert p.grammar == "mathema/language"
    assert p.meta["mathema.language"]["s"][0]["source"].startswith("entry point")


def test_an_encoding_boundary_falsifies_with_the_member_as_witness(tmp_path):
    mod = _load(tmp_path, '''
        def ascii_only(s: str) -> str:
            """The text, if ascii."""
            return s.encode("ascii").decode("ascii")
    ''')
    (p,) = check_conjectures(mod.ascii_only, [claim("for s in L[latin-1], f(s) == s")])
    assert p.verdict == "falsified" and "UnicodeEncodeError" in p.counterexample
    (q,) = check_conjectures(mod.ascii_only, [claim("for s in L[ascii], f(s) == s")])
    assert q.verdict == "holds"


def test_upper_case_is_not_length_preserving_over_unicode(tmp_path):
    mod = _load(tmp_path, '''
        def shout(s: str) -> str:
            """Upper case."""
            return s.upper()
    ''')
    (p,) = check_conjectures(mod.shout, [claim("for s in L[unicode], len(f(s)) == len(s)")])
    assert p.verdict == "falsified", (p.verdict, p.note)


def test_an_unknown_name_is_still_refused():
    with pytest.raises(UnknownLanguage, match="L\\[nope\\]"):
        resolve(LanguageRef("nope"))


def test_the_families_are_discovered_and_parse():
    from mathema import families, routes
    from mathema.claim_families import _ACCIDENTAL_CRASHES

    from mathema_language.families import ACCIDENTAL_CRASHES

    assert {"is_length_safe", "is_encoding_safe"} <= set(families.families())
    assert {"is_length_safe", "is_encoding_safe"} <= routes.safety_predicates()
    # an output is held to a language with `in`; the package adds no output predicate
    assert "output_in_language" not in routes.output_predicates()
    assert claim("is_length_safe(s)").relation == "is_length_safe"
    assert claim("s is encoding safe").relation == "is_encoding_safe"
    # the crash taxonomy is the same seven types mathema's own fuzz counts
    assert set(ACCIDENTAL_CRASHES) == set(_ACCIDENTAL_CRASHES)


def test_a_str_annotation_infers_the_unicode_language(tmp_path):
    import importlib.util
    import textwrap

    p = tmp_path / "infer_fns.py"
    p.write_text(textwrap.dedent('''
        def same(s: str) -> str:
            """The text, unchanged."""
            return s
    '''))
    spec = importlib.util.spec_from_file_location("infer_fns", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    (r,) = check_conjectures(mod.same, [claim("f(s) == s", route="probe")])
    assert r.verdict == "holds", (r.verdict, r.note)
    assert "L[unicode]" in r.note and "adaptor" in r.note, r.note
    # the stamp reads the stated domain: an inferred language enriches
    # the record without promoting the claim to the dialect
    assert r.grammar == "mathema"


ORDER_MODULE = '''
    from dataclasses import dataclass
    from typing import Annotated


    class Ge:
        def __init__(self, ge):
            self.ge = ge


    class Le:
        def __init__(self, le):
            self.le = le


    @dataclass
    class Order:
        qty: Annotated[int, Ge(1), Le(10)]
        price: Annotated[float, Ge(0.0), Le(1000.0)]


    def total(o: Order) -> float:
        """Quantity times price."""
        return o.qty * o.price
'''


def _module(tmp_path, name, body):
    import importlib.util
    import sys
    import textwrap

    p = tmp_path / f"{name}.py"
    p.write_text(textwrap.dedent(body))
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_a_dataclass_resolves_through_the_dataclass_entry_point(tmp_path):
    mod = _module(tmp_path, "schema_orders_ep", ORDER_MODULE)
    (p,) = check_conjectures(mod.total, [claim(
        "for o in L[schema_orders_ep.Order], f(o) >= 0", route="probe")])
    assert p.verdict == "holds", (p.verdict, p.note, p.counterexample)
    described = p.meta["mathema.language"]["o"][0]
    assert described["source"] == "adaptor dataclass" and described["kind"] == "row"
    assert described["schema"]["properties"]["qty"] == {"type": "integer", "minimum": 1, "maximum": 10}


def test_a_dataclass_annotation_infers_its_row_language(tmp_path):
    mod = _module(tmp_path, "schema_orders_infer", ORDER_MODULE)
    (p,) = check_conjectures(mod.total, [claim("f(o) >= 0", route="probe")])
    assert p.verdict == "holds", (p.verdict, p.note, p.counterexample)
    assert "inferred o in L[schema_orders_infer.Order]" in p.note, p.note
    assert "adaptor dataclass" in p.note


def test_the_field_lift_proves_a_sign_fact_over_a_row_language(tmp_path):
    mod = _module(tmp_path, "schema_orders_lift", ORDER_MODULE)
    (p,) = check_conjectures(mod.total, [claim(
        "for o in L[schema_orders_lift.Order], f(o) >= 0", route="derive")])
    assert p.verdict in ("proven", "holds", "unknown"), (p.verdict, p.note)
    if p.verdict != "proven":
        assert p.meta.get("mathema.timeout"), (p.verdict, p.note, p.meta)


def test_an_executed_instance_is_the_disproof(tmp_path):
    mod = _module(tmp_path, "schema_orders_dis", ORDER_MODULE)
    (p,) = check_conjectures(mod.total, [claim(
        "for o in L[schema_orders_dis.Order], f(o) <= 50")])
    assert p.verdict == "falsified", (p.verdict, p.note)
    assert "Order(" in str(p.counterexample)


MIXED_MODULE = '''
    from dataclasses import dataclass
    from typing import Annotated, Literal


    class Ge:
        def __init__(self, ge):
            self.ge = ge


    class Le:
        def __init__(self, le):
            self.le = le


    class MaxLen:
        def __init__(self, max_length):
            self.max_length = max_length


    @dataclass
    class Order:
        id: int
        kind: Literal["web", "shop"]
        qty: Annotated[int, Ge(1), Le(10)]
        price: Annotated[float, Ge(0.0)]
        sku: Annotated[str, MaxLen(8)]
        note: str | None = None


    def total(o: Order) -> float:
        """Quantity times price."""
        return o.qty * o.price


    def labelled(o: Order) -> float:
        """Quantity times price, plus one per character of the sku."""
        return o.qty * o.price + len(o.sku)


    def by_kind(o: Order) -> float:
        """Web orders pay a flat two on top."""
        return o.qty * o.price + (2.0 if o.kind == "web" else 0.0)
'''


def test_the_lift_proves_over_a_row_with_fields_the_body_never_reads(tmp_path):
    mod = _module(tmp_path, "schema_mixed", MIXED_MODULE)
    for fn in (mod.total, mod.labelled):
        (p,) = check_conjectures(fn, [claim(
            "for o in L[schema_mixed.Order], f(o) >= 0", route="derive")])
        if p.verdict != "proven":
            assert p.meta.get("mathema.timeout"), (fn.__name__, p.verdict, p.note, p.sketch)
    (q,) = check_conjectures(mod.by_kind, [claim(
        "for o in L[schema_mixed.Order], f(o) >= 0", route="derive")])
    assert q.verdict != "proven" and "o.kind" in (q.note or "") + str(q.sketch or "")
