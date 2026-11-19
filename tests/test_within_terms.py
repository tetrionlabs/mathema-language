# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Each `within` language carries a regular-language term of itself
under `definition` in its persisted form. The term is exact for paths,
IP blocks, date intervals and URL regions: the term's matcher and the
language agree on members, boundary values and near text. A datetime
interval states a pair instead, and every member is in `at_least` and
everything in `at_most` is a member. A region inside another is seen on
the terms: every draw and boundary value of the smaller is in the
larger's term, and a named witness is in the larger's and not the
smaller's. The word's own description names the base languages it has a
meaning for, checks an argument's form, and suggests the claim that was
meant when it is refused."""
import json
import random

import mathema.languages as languages
import pytest

from mathema_language.text import _regular
from mathema_language.text.path_language import PATH, path_within
from mathema_language.text.url_language import URL
from mathema_language.text.within import (
    WITHIN,
    claim_text,
    ipv4_within,
    ipv6_within,
    iso_date_within,
    iso_datetime_within,
    suggest_within,
    url_within,
    within,
    within_examples,
    within_refusal,
)

EXACT = {
    "paths": lambda: path_within("/workspace", "/data"),
    "path": lambda: path_within("/workspace"),
    "ipv4": lambda: ipv4_within("10.0.0.0/8", "192.168.4.0/22"),
    "ipv6": lambda: ipv6_within("2001:db8::/32", "fe80::/10"),
    "iso_date": lambda: iso_date_within("2024-02-27", "2026-12-31"),
    "url origin": lambda: url_within("https://example.com"),
    "url prefix": lambda: url_within("https://example.com/api", "http://localhost:3000"),
}


def _corpus(language, n: int = 60) -> list[str]:
    """Draws, boundary members and values just outside `language`, with
    the base language's own draws."""
    rng = random.Random(11)
    base = getattr(language, "base", None) or PATH
    texts = [language.sample(rng) for _ in range(n)] + [h.value for h in language.hazards()]
    texts += [t for t in (language.outside(random.Random(s)) for s in range(n)) if t is not None]
    texts += [getattr(h, "value", h) for h in getattr(language, "near", ())]
    texts += [base.sample(rng) for _ in range(n)] + [h.value for h in base.hazards()]
    return [t for t in texts if isinstance(t, str) and len(t) < 200]


@pytest.mark.parametrize("build", EXACT.values(), ids=list(EXACT))
def test_the_term_is_exact_and_its_matcher_agrees_with_the_language(build):
    language = build()
    doc = language.to_json()["definition"]
    assert doc["kind"] == "regular_language" and doc["exact"] is True
    assert json.loads(json.dumps(doc)) == doc
    texts = _corpus(language)
    assert any(language.contains(t) for t in texts) and not all(language.contains(t) for t in texts)
    for text in texts:
        assert _regular.member(doc, text) == language.contains(text), text


def test_the_path_language_itself_states_its_term():
    doc = PATH.to_json()["definition"]
    assert doc["exact"] is True
    for text in ["a", "/", "a\nb", "", "a\x00b"]:
        assert _regular.member(doc, text) == PATH.contains(text)


def test_the_url_language_states_its_term():
    doc = URL.to_json()["definition"]
    assert doc["exact"] is True
    rng = random.Random(12)
    texts = [URL.sample(rng) for _ in range(60)] + [h.value for h in URL.hazards()]
    texts += [URL.outside(random.Random(s)) for s in range(40)]
    for text in texts:
        assert _regular.member(doc, text) == URL.contains(text), text


def test_one_region_hashes_the_same_however_it_is_built_and_another_differently():
    one = _regular.term_hash(ipv4_within("10.0.0.0/8").definition())
    assert one == _regular.term_hash(within(languages.resolve_language("ipv4"), "10.0.0.0/8").definition())
    assert one != _regular.term_hash(ipv4_within("10.0.0.0/9").definition())
    assert (_regular.term_hash(path_within("/workspace").definition())
            != _regular.term_hash(path_within("/workspace2").definition()))


@pytest.mark.parametrize("lo, hi, some_most", [
    ("2026-11-19T09:00:00", "2026-11-19T17:30:00", True),
    ("2026-11-19T09:00:00+00:00", "2026-11-21T17:30:00+00:00", True),
    ("2026-11-19T23:59:58.5-08:00", "2026-11-20T00:00:03-08:00", True),
    ("2026-11-19T09:00:00.250000-08:00", "2026-11-19T09:00:00.250000-08:00", False),
    ("0001-01-01T00:00:00+00:00", "0001-01-01T12:00:00+00:00", True),
    ("9999-12-31T23:59:58", "9999-12-31T23:59:59.999999", True),
], ids=repr)
def test_a_datetime_interval_states_bounds_around_its_members(lo, hi, some_most):
    language = iso_datetime_within(lo, hi)
    doc = language.to_json()["definition"]
    assert doc["exact"] is False and "language" not in doc
    assert json.loads(json.dumps(doc)) == doc
    texts = _corpus(language, 80)
    texts += [lo, hi, lo.replace("T", "\n"), lo[:10] + "T23:59:59" + lo[19:].lstrip(".0123456789")]
    members = [t for t in texts if language.contains(t)]
    assert members
    for text in members:
        assert _regular.member(doc, text, "at_least"), text
    most = [t for t in texts if _regular.member(doc, t, "at_most")]
    assert bool(most) == some_most
    for text in most:
        assert language.contains(text), text


def _inside(small, large, witness: str) -> None:
    """Every draw and boundary value of `small` is in `large`'s term, and
    `witness` is in `large`'s term and not in `small`'s."""
    a, b = small.definition(), large.definition()
    rng = random.Random(14)
    for text in [small.sample(rng) for _ in range(200)] + [h.value for h in small.hazards()]:
        assert _regular.member(a, text) and _regular.member(b, text), text
    assert _regular.member(b, witness) and not _regular.member(a, witness)
    assert large.contains(witness) and not small.contains(witness)


@pytest.mark.parametrize("small, large, witness", [
    (lambda: path_within("/workspace/src"), lambda: path_within("/workspace"), "/workspace/README.md"),
    (lambda: path_within("/workspace"), lambda: path_within("/workspace", "/data"), "/data/x"),
    (lambda: ipv4_within("10.1.0.0/16"), lambda: ipv4_within("10.0.0.0/8"), "10.2.0.0"),
    (lambda: ipv4_within("10.1.0.0/16"), lambda: ipv4_within("10.0.0.0/8"), "10.0.255.255"),
    (lambda: ipv6_within("2001:db8:1::/48"), lambda: ipv6_within("2001:db8::/32"), "2001:db8:2::1"),
    (lambda: iso_date_within("2026-03-01", "2026-03-31"), lambda: iso_date_within("2026-01-01", "2026-12-31"),
     "2026-04-01"),
    (lambda: url_within("https://example.com/api"), lambda: url_within("https://example.com"),
     "https://example.com/admin"),
    (lambda: url_within("https://example.com/api/v1"), lambda: url_within("https://example.com/api"),
     "https://example.com/api/v2"),
], ids=["path subtree", "path union", "cidr after", "cidr before", "ipv6", "dates", "url origin", "url prefix"])
def test_a_region_inside_another_is_inside_on_the_terms_and_not_the_converse(small, large, witness):
    _inside(small(), large(), witness)


# --- the word's own description


def test_every_example_builds_and_names_itself():
    examples = within_examples()
    assert examples == {
        "path": 'L[path, within ("/workspace")]',
        "ipv4": 'L[ipv4, within ("10.0.0.0/8")]',
        "ipv6": 'L[ipv6, within ("2001:db8::/32")]',
        "iso_date": 'L[iso_date, within ("2026-01-01", "2026-12-31")]',
        "iso_datetime": 'L[iso_datetime, within ("2026-01-01T00:00:00", "2026-12-31T23:59:59")]',
    }
    for base, kind in WITHIN.items():
        assert within_refusal(base, kind.example) is None
        built = kind.build(*kind.example)
        assert languages.language_problems(built) == []
        if kind.registered:
            assert languages.resolve_language(base).name == base
            if base != "path":
                assert "L[" + built.name + "]" == examples[base]
    assert not WITHIN["url"].registered and "url" not in examples


@pytest.mark.parametrize("base, arguments, said", [
    ("ipv4", ("/root",), 'within ("/root") is not an address block for L[ipv4]: it expects a CIDR block '
                         'such as "10.0.0.0/8"'),
    ("ipv4", ("10.1.2.3/8",), "CIDR block"),
    ("ipv6", ("10.0.0.0/8",), 'a CIDR block such as "2001:db8::/32"'),
    ("path", ("workspace",), 'it expects an absolute path such as "/workspace"'),
    ("iso_date", ("2026-01-01",), "takes 2 arguments, an interval of dates, not 1"),
    ("iso_date", ("2026-01-01", "tomorrow"), 'it expects an ISO date such as "2026-01-01"'),
    ("iso_date", ("2026-12-31", "2026-01-01"), "an interval runs from a date to one no earlier"),
    ("iso_datetime", ("2026-01-01T00:00:00", "2026-01-02T00:00:00+00:00"), "both naive or both aware"),
    ("url", ("https://user@example.com",), "a URL with no user, query or fragment"),
    ("unicode", ("/workspace",), "'within' has no meaning for L[unicode]: it bounds a path, an IPv4 address, "
                                 "an IPv6 address, a date or a datetime"),
    ("path", (), "at least one argument"),
])
def test_a_refusal_names_the_form_the_base_expects(base, arguments, said):
    assert said in within_refusal(base, arguments)


@pytest.mark.parametrize("base, arguments", [
    ("path", ("/workspace", "/data")), ("ipv4", ("10.0.0.0/8", "192.168.0.0/16")), ("ipv6", ("::/0",)),
    ("iso_date", ("2026-01-01", "2026-01-01")),
    ("iso_datetime", ("2026-01-01T00:00:00Z", "2026-01-02T00:00:00+01:00")),
    ("url", ("https://example.com", "https://example.com/api/")),
])
def test_arguments_of_the_right_form_are_not_refused_and_nothing_is_suggested(base, arguments):
    assert within_refusal(base, arguments) is None
    assert suggest_within(base, arguments) == ()


@pytest.mark.parametrize("base, arguments, suggested", [
    ("unicode", ("/workspace",), ('L[path, within ("/workspace")]', 'L[unicode, starts with ("/workspace")]')),
    ("ipv4", ("/root",), ('L[path, within ("/root")]', 'L[ipv4, within ("10.0.0.0/8")]')),
    ("unicode", ("10.0.0.0/8",), ('L[ipv4, within ("10.0.0.0/8")]', 'L[unicode, starts with ("10.0.0.0/8")]')),
    ("ipv4", ("2001:db8::/32",), ('L[ipv6, within ("2001:db8::/32")]', 'L[ipv4, within ("10.0.0.0/8")]')),
    ("path", ("10.0.0.0/8", "10.1.0.0/16"), ('L[ipv4, within ("10.0.0.0/8", "10.1.0.0/16")]',
                                             'L[path, within ("/workspace")]')),
    ("unicode", ("2026-01-01", "2026-12-31"), ('L[iso_date, within ("2026-01-01", "2026-12-31")]',
                                               'L[iso_datetime, within ("2026-01-01", "2026-12-31")]')),
    ("iso_date", ("2026-01-01T09:00:00", "2026-01-01T17:00:00"),
     ('L[iso_datetime, within ("2026-01-01T09:00:00", "2026-01-01T17:00:00")]',
      'L[iso_date, within ("2026-01-01", "2026-12-31")]')),
    ("iso_date", ("2026-01-01",), ('L[iso_date, within ("2026-01-01", "2026-12-31")]',)),
    ("slug", ("abc",), ('L[slug, starts with ("abc")]',)),
    ("slug", ("abc", "def"), ()),
    ("unicode", ('say "hi"',), ('L[unicode, starts with ("say \\"hi\\"")]',)),
    ("unicode", ("https://example.com/api",), ('L[unicode, starts with ("https://example.com/api")]',)),
    ("url", ("/api",), ('L[path, within ("/api")]',)),
])
def test_a_refused_use_suggests_the_claim_that_was_meant(base, arguments, suggested):
    assert within_refusal(base, arguments) is not None
    assert suggest_within(base, arguments) == suggested


def test_every_suggested_within_names_a_language_that_builds():
    for base, arguments in [("unicode", ("/workspace",)), ("ipv4", ("/root",)), ("path", ("10.0.0.0/8",)),
                            ("unicode", ("2026-01-01", "2026-12-31")), ("ipv4", ("fe80::/10",))]:
        for text in suggest_within(base, arguments):
            if ", within (" not in text:
                continue
            name = text[2:text.index(",")]
            assert text == claim_text(name, "within", arguments) or text == within_examples()[name]
            regions = arguments if text == claim_text(name, "within", arguments) else WITHIN[name].example
            assert languages.language_problems(WITHIN[name].build(*regions)) == []
