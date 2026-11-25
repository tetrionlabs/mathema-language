# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""`within` bounds a text language to a region whose meaning the base
language sets: a subtree for paths, CIDR blocks for IP addresses, a
closed interval for ISO dates and datetimes, an origin or a path prefix
for URLs; several regions are their union. Membership is checked here
against the standard library (`posixpath`, `ipaddress`, `datetime`,
`urllib.parse`) on pinned cases at each boundary and on drawn text, the
draws are members, the near values are not, and where a language states
a pattern, the pattern read in full admits exactly the members."""
import datetime as dt
import ipaddress
import posixpath
import random
import re
from urllib.parse import urlsplit

import mathema.languages as languages
import pytest

from mathema_language.text import IPV4, IPV6, ISO_DATE, ISO_DATETIME
from mathema_language.text._finite import finite_complement, finite_pattern
from mathema_language.text.path_language import PATH, path_within, within_pattern
from mathema_language.text.url_language import URL, URL_PATTERN
from mathema_language.text.within import (
    WithinLanguage,
    ipv4_within,
    ipv6_within,
    iso_date_within,
    iso_datetime_within,
    url_within,
    within,
)


def _mutations(rng: random.Random, text: str, alphabet: str, n: int) -> list[str]:
    """`n` strings one edit away from `text`: a character of `alphabet`
    inserted or substituted, or a character deleted."""
    out = []
    for _ in range(n):
        at = rng.randint(0, len(text))
        kind = rng.random()
        if kind < 0.4:
            out.append(text[:at] + rng.choice(alphabet) + text[at:])
        elif kind < 0.8 and text:
            at = min(at, len(text) - 1)
            out.append(text[:at] + rng.choice(alphabet) + text[at + 1:])
        else:
            out.append(text[:at] + text[at + 1:])
    return out


def _agree(language: WithinLanguage, texts) -> None:
    """The language's pattern, read in full, admits exactly the members
    among `texts`."""
    compiled = re.compile(language.pattern)
    for text in texts:
        assert (compiled.fullmatch(text) is not None) == language.contains(text), (language.name, text)


def _draws_hold(language, seeds: int = 60) -> None:
    rng = random.Random(0)
    assert all(language.contains(language.sample(rng)) for _ in range(seeds))
    assert all(language.contains(h.value) for h in language.hazards())
    for seed in range(seeds):
        outside = language.outside(random.Random(seed))
        assert outside is None or not language.contains(outside), outside


# --- finite sets as patterns


@pytest.mark.parametrize("words", [
    {"a"}, {"", "a"}, {"ab", "ac", "b"}, {str(i) for i in range(0, 256)},
    {str(i) for i in range(17, 132)}, {f"{i:04d}" for i in range(1896, 2105, 4)},
    {"W01", "W01-1", "W53-7"}, {"a.b", "a-b", "a]b", "a^b", "a\\b"},
], ids=lambda words: repr(sorted(words))[:60])
def test_a_finite_pattern_admits_exactly_its_words(words):
    compiled = re.compile(finite_pattern(words))
    rng = random.Random(1)
    alphabet = "".join(sorted(set("".join(words)) | set("0a")))
    near = [m for w in sorted(words) for m in _mutations(rng, w, alphabet, 20)]
    for text in [*words, *near, ""]:
        assert (compiled.fullmatch(text) is not None) == (text in words), text


def test_a_folded_finite_pattern_admits_either_case():
    compiled = re.compile(finite_pattern({"0a", "ff"}, fold=True))
    assert all(compiled.fullmatch(t) for t in ("0a", "0A", "ff", "Ff", "fF", "FF"))
    assert not any(compiled.fullmatch(t) for t in ("0b", "a", "0aa"))


def test_a_finite_pattern_of_no_words_is_refused():
    with pytest.raises(ValueError):
        finite_pattern(set())


def test_a_finite_complement_admits_every_other_word_over_the_alphabet():
    words = {"..", ".%2e", "%2e.", "%2e%2e"}
    compiled = re.compile(finite_complement(words, excluded="/?#"))
    rng = random.Random(2)
    near = [m for w in sorted(words) for m in _mutations(rng, w, ".%2e/a?", 60)]
    for text in [*words, *near, "", "a", "...", "%2e%2e%2e"]:
        over_alphabet = not any(c in "/?#" for c in text)
        assert (compiled.fullmatch(text) is not None) == (over_alphabet and text not in words), text


# --- paths: a subtree, or several


def _path_reference(text: str, roots: tuple[str, ...]) -> bool:
    """Whether `text` is a path within the roots, by `posixpath`:
    non-empty text with no NUL and no `..` segment, relative, or
    absolute and one of the roots or below one."""
    if text == "" or "\x00" in text or ".." in text.split("/"):
        return False
    if not posixpath.isabs(text):
        return True
    for root in roots:
        if root == "/":
            if text == "/" or not text.startswith("//"):
                return True
        elif text == root or text.startswith(root + "/"):
            return True
    return False


PATH_CASES = ["a", "a/b", ".", "/workspace", "/workspace/", "/workspace/src/a.py", "/workspace2",
              "/workspace2/a", "/workspac", "/data", "/data/x", "/dat", "/", "//workspace",
              "/workspace/../etc", "../workspace", "/workspace/..", "", "a\x00", "/datax"]


def test_one_root_reads_as_it_did_and_several_roots_are_their_union():
    one, two = path_within("/workspace"), path_within("/workspace", "/data/")
    assert one.name == 'path, within ("/workspace")'
    assert two.name == 'path, within ("/workspace", "/data")'
    assert languages.language_problems(two) == []
    rng = random.Random(3)
    texts = PATH_CASES + [m for c in PATH_CASES for m in _mutations(rng, c, "/.a2", 30)]
    for text in texts:
        assert one.contains(text) == _path_reference(text, ("/workspace",)), text
        assert two.contains(text) == _path_reference(text, ("/workspace", "/data")), text
        assert two.contains(text) == (one.contains(text) or path_within("/data").contains(text))
    assert within_pattern("/workspace") == one.pattern


def test_a_path_draw_beside_the_boundary_is_a_sibling_prefix_or_a_climb():
    language = path_within("/workspace", "/data")
    _draws_hold(language)
    drawn = {language.outside(random.Random(seed)) for seed in range(200)}
    assert {"/workspace2", "/datax", "/workspac"} <= drawn
    assert any(h.value == "/workspace" for h in language.hazards())


def test_within_on_the_path_language_is_path_within():
    assert within(PATH, "/workspace", "/data").name == path_within("/workspace", "/data").name
    with pytest.raises(ValueError):
        path_within("/a", "relative")


# --- IP addresses: CIDR blocks


def _ip_reference(text: str, blocks: tuple[str, ...]) -> bool:
    try:
        address = ipaddress.ip_address(text)
    except ValueError:
        return False
    return any(address.version == ipaddress.ip_network(b).version and address in ipaddress.ip_network(b)
               for b in blocks)


V4 = {
    "10.0.0.0": True, "10.255.255.255": True, "10.1.2.3": True, "9.255.255.255": False,
    "11.0.0.0": False, "010.1.2.3": False, "10.1.2": False, "10.1.2.3 ": False, "10.1.2.3/8": False,
    "::ffff:10.1.2.3": False, "١٠.1.2.3": False, "": False,
}


@pytest.mark.parametrize("text, inside", V4.items(), ids=repr)
def test_an_ipv4_block_admits_exactly_its_addresses(text, inside):
    block = ipv4_within("10.0.0.0/8")
    assert block.contains(text) == inside == _ip_reference(text, ("10.0.0.0/8",))
    assert IPV4.contains(text) or not inside


@pytest.mark.parametrize("blocks", [
    ("10.0.0.0/8",), ("10.1.0.0/16",), ("192.168.4.0/22",), ("10.0.0.0/8", "192.168.0.0/16"),
    ("203.0.113.7/32",), ("0.0.0.0/0",), ("128.0.0.0/1",), ("10.64.0.0/10", "10.128.0.0/9"),
    ("255.255.255.254/31",), ("0.0.0.0/31",),
], ids=repr)
def test_ipv4_blocks_agree_with_ipaddress_and_with_their_pattern(blocks):
    language = ipv4_within(*blocks)
    assert languages.language_problems(language) == []
    rng = random.Random(4)
    texts = list(V4)
    for block in map(ipaddress.ip_network, blocks):
        first, last = int(block.network_address), int(block.broadcast_address)
        edge = {first, last, first + 1, last - 1, first - 1, last + 1, rng.randint(first, last)}
        texts += [str(ipaddress.IPv4Address(i)) for i in edge if 0 <= i < 2 ** 32]
    texts += [str(ipaddress.IPv4Address(rng.getrandbits(32))) for _ in range(300)]
    texts += [m for t in list(texts) for m in _mutations(rng, t, "0123456789.", 4)]
    for text in texts:
        assert language.contains(text) == _ip_reference(text, blocks), text
    _agree(language, texts)
    _draws_hold(language)


def test_an_ipv4_draw_beside_the_boundary_is_the_address_before_or_after_the_block():
    language = ipv4_within("10.1.0.0/16")
    assert language.name == 'ipv4, within ("10.1.0.0/16")'
    assert {"10.1.0.0", "10.1.255.255"} <= {h.value for h in language.hazards()}
    drawn = {language.outside(random.Random(seed)) for seed in range(200)}
    assert {"10.0.255.255", "10.2.0.0"} <= drawn


@pytest.mark.parametrize("block", ["10.1.2.3/8", "10.0.0.0/33", "fe80::/10", "ten", "", "10.0.0.0/8 "])
def test_an_ipv4_block_is_named_by_its_network_address(block):
    with pytest.raises(ValueError):
        ipv4_within(block)


V6 = {
    "2001:db8::": True, "2001:db8::1": True, "2001:0db8:0000:0000:0000:0000:0000:0001": True,
    "2001:DB8::1": True, "2001:db8:ffff:ffff:ffff:ffff:ffff:ffff": True,
    "2001:db8::1.2.3.4": True, "2001:db8:0:0:0:0:1.2.3.4": True, "2001:db8::1%eth0": True,
    "2001:db7:ffff:ffff:ffff:ffff:ffff:ffff": False, "2001:db9::": False, "2001:db8:::1": False,
    "2001:db8::1%": False, "2001:db8": False, "::": False, "2001:db8::01.2.3.4": False,
    "02001:db8::": False, "2001:db8::1/32": False, "10.0.0.1": False, "": False,
}


@pytest.mark.parametrize("text, inside", V6.items(), ids=repr)
def test_an_ipv6_block_admits_every_spelling_of_its_addresses(text, inside):
    block = ipv6_within("2001:db8::/32")
    assert block.contains(text) == inside == _ip_reference(text, ("2001:db8::/32",))
    assert IPV6.contains(text) or not inside


def _v6_spellings(rng: random.Random, value: int) -> list[str]:
    """Several spellings of one IPv6 address: compressed, exploded, upper
    case, with an IPv4 tail, with a scope, and with `::` standing for a
    single zero group where it has one."""
    address = ipaddress.IPv6Address(value)
    groups = [f"{(value >> shift) & 0xFFFF:04x}" for shift in range(112, -1, -16)]
    out = [str(address), ":".join(groups), ":".join(groups).upper(),
           ":".join(g.lstrip("0") or "0" for g in groups), str(address) + "%eth0",
           ":".join(groups[:6]) + ":" + str(ipaddress.IPv4Address(value & 0xFFFFFFFF))]
    zeros = [i for i, g in enumerate(groups) if int(g, 16) == 0]
    if zeros:
        i = rng.choice(zeros)
        out.append(":".join(groups[:i]) + "::" + ":".join(groups[i + 1:]))
    return out


@pytest.mark.parametrize("blocks", [
    ("2001:db8::/32",), ("fe80::/10",), ("::/0",), ("::1/128",), ("::/127",), ("fc00::/7", "fe80::/10"),
    ("2001:db8:0:8000::/49",), ("::ffff:0:0/96",), ("64:ff9b::/96",), ("2001:db8::/29",),
    ("ffff:ffff:ffff:ffff:ffff:ffff:ffff:fff0/124",), ("0:0:0:1::/64",), ("::102:300/120",),
], ids=repr)
def test_ipv6_blocks_agree_with_ipaddress_and_with_their_pattern(blocks):
    language = ipv6_within(*blocks)
    assert languages.language_problems(language) == []
    rng = random.Random(5)
    values = [rng.getrandbits(128) for _ in range(40)] + [0, 1, 2 ** 128 - 1]
    for block in map(ipaddress.ip_network, blocks):
        first, last = int(block.network_address), int(block.broadcast_address)
        edge = {first, last, first + 1, last - 1, first - 1, last + 1}
        edge |= {rng.randint(first, last) for _ in range(10)}
        edge |= {first | rng.getrandbits(16) << (16 * rng.randrange(8)) for _ in range(10)}
        values += [i for i in edge if 0 <= i < 2 ** 128]
    texts = list(V6) + [s for v in values for s in _v6_spellings(rng, v)]
    texts += [m for t in list(texts) for m in _mutations(rng, t, "0123456789abcdefF:.%", 3)]
    for text in texts:
        assert language.contains(text) == _ip_reference(text, blocks), text
    _agree(language, texts)
    _draws_hold(language)


def test_an_ipv6_draw_beside_the_boundary_is_the_address_before_or_after_the_block():
    language = ipv6_within("2001:db8::/32")
    assert language.name == 'ipv6, within ("2001:db8::/32")'
    assert {"2001:db8::", "2001:db8:ffff:ffff:ffff:ffff:ffff:ffff"} <= {h.value for h in language.hazards()}
    drawn = {language.outside(random.Random(seed)) for seed in range(200)}
    assert {"2001:db7:ffff:ffff:ffff:ffff:ffff:ffff", "2001:db9::"} <= drawn


def test_blocks_of_the_other_version_are_refused():
    with pytest.raises(ValueError):
        ipv6_within("10.0.0.0/8")
    with pytest.raises(ValueError):
        within(IPV6, "2001:db8::1/32")
    assert within(IPV4, "10.0.0.0/8").name == ipv4_within("10.0.0.0/8").name
    assert within(IPV6, "fe80::/10").name == ipv6_within("fe80::/10").name


# --- ISO dates: a closed interval


def _date_reference(text: str, lo: dt.date, hi: dt.date) -> bool:
    try:
        return lo <= dt.date.fromisoformat(text) <= hi
    except ValueError:
        return False


def _date_spellings(day: dt.date) -> list[str]:
    """Every ISO 8601 spelling of `day` a standard parser may read:
    extended and basic calendar dates, and extended and basic week dates
    with and without the day."""
    year, week, weekday = day.isocalendar()
    return [day.isoformat(), f"{day.year:04d}{day.month:02d}{day.day:02d}",
            f"{year:04d}-W{week:02d}-{weekday}", f"{year:04d}W{week:02d}{weekday}",
            f"{year:04d}-W{week:02d}", f"{year:04d}W{week:02d}"]


DATE_INTERVALS = [
    ("2026-01-01", "2026-12-31"), ("2026-11-19", "2026-11-19"), ("2024-02-28", "2024-03-01"),
    ("2023-02-27", "2023-03-02"), ("2020-12-27", "2021-01-05"), ("2026-12-27", "2027-01-05"),
    ("1999-06-15", "2104-02-29"), ("0001-01-01", "0001-01-09"), ("9999-12-20", "9999-12-31"),
    ("0001-01-01", "9999-12-31"), ("1900-02-27", "1900-03-01"), ("2000-02-27", "2000-03-01"),
    ("2026-03-30", "2026-04-02"), ("2015-12-31", "2016-01-01"),
]


@pytest.mark.parametrize("lo, hi", DATE_INTERVALS, ids=repr)
def test_a_date_interval_agrees_with_datetime_and_with_its_pattern(lo, hi):
    language = iso_date_within(lo, hi)
    first, last = dt.date.fromisoformat(lo), dt.date.fromisoformat(hi)
    assert language.name == f'iso_date, within ("{lo}", "{hi}")'
    assert languages.language_problems(language) == []
    rng = random.Random(6)
    days = set()
    for edge in (first, last):
        for delta in range(-9, 10):
            ordinal = edge.toordinal() + delta
            if dt.date.min.toordinal() <= ordinal <= dt.date.max.toordinal():
                days.add(dt.date.fromordinal(ordinal))
    days |= {dt.date.fromordinal(rng.randint(first.toordinal(), last.toordinal())) for _ in range(40)}
    days |= {dt.date.fromordinal(rng.randint(1, dt.date.max.toordinal())) for _ in range(40)}
    days |= {dt.date(y, 12, 28) for y in (first.year, last.year, 2020, 2026)}
    texts = [s for day in sorted(days) for s in _date_spellings(day)]
    texts += [f"{y:04d}-W53-{d}" for y in (first.year, last.year, 2020, 2021, 2026) for d in (1, 7)]
    texts += [f"{y:04d}-02-29" for y in (first.year, last.year, 1900, 2000, 2023, 2024)]
    texts += [m for t in list(texts) for m in _mutations(rng, t, "0123456789-W", 3)]
    texts += ["", "2026-13-01", "2026-00-10", "2026-01-32", "2026-W00-1", "2026-W01-8", "2026-W01-0",
              "２０２６-01-01", "2026-01-01\n", "2026-1-1", "+2026-01-01"]
    for text in texts:
        assert language.contains(text) == _date_reference(text, first, last), text
        assert ISO_DATE.contains(text) or not language.contains(text)
    _agree(language, texts)
    _draws_hold(language)


def test_a_date_draw_beside_the_boundary_is_the_day_before_or_after():
    language = iso_date_within(dt.date(2026, 1, 1), "2026-12-31")
    assert {"2026-01-01", "2026-12-31"} <= {h.value for h in language.hazards()}
    drawn = {language.outside(random.Random(seed)) for seed in range(200)}
    assert {"2025-12-31", "2027-01-01"} <= drawn
    assert within(ISO_DATE, "2026-01-01", "2026-12-31").name == language.name


@pytest.mark.parametrize("lo, hi", [("2026-12-31", "2026-01-01"), ("2026-01-01", "soon"),
                                    ("2026-01-01T00:00:00", "2026-01-02T00:00:00")])
def test_a_date_interval_runs_from_a_date_to_a_date_no_earlier(lo, hi):
    with pytest.raises(ValueError):
        iso_date_within(lo, hi)


def test_a_date_interval_takes_two_bounds():
    with pytest.raises(TypeError):
        within(ISO_DATE, "2026-01-01")


# --- ISO datetimes: a closed interval of naive datetimes, or of instants


def _datetime_reference(text: str, lo: dt.datetime, hi: dt.datetime) -> bool:
    try:
        value = dt.datetime.fromisoformat(text)
    except ValueError:
        return False
    if (value.tzinfo is None) != (lo.tzinfo is None):
        return False
    return lo <= value <= hi


NAIVE = {
    "2026-11-19T09:00:00": True, "2026-11-19T17:30:00": True, "2026-11-19T12:00": True,
    "2026-11-19 12:00:00.5": True, "2026-11-19T08:59:59.999999": False, "2026-11-19T17:30:00.000001": False,
    "2026-11-19": False, "2026-11-19T12:00:00+00:00": False, "2026-11-19T12:00:00Z": False,
    "2026-11-20T09:00:00": False, "noon": False, "": False,
}


@pytest.mark.parametrize("text, inside", NAIVE.items(), ids=repr)
def test_a_naive_interval_admits_naive_datetimes_between_its_bounds(text, inside):
    lo, hi = dt.datetime(2026, 11, 19, 9), dt.datetime(2026, 11, 19, 17, 30)
    language = iso_datetime_within("2026-11-19T09:00:00", "2026-11-19T17:30:00")
    expected = inside and ISO_DATETIME.contains(text)
    assert language.contains(text) == expected == _datetime_reference(text, lo, hi)


AWARE = {
    "2026-11-19T09:00:00+00:00": True, "2026-11-19T10:00:00+01:00": True, "2026-11-19T04:00:00-05:00": True,
    "2026-11-19T17:30:00+00:00": True, "2026-11-20T03:30:00+10:00": True,
    "2026-11-19T09:00:00+01:00": False, "2026-11-19T17:30:00.000001+00:00": False,
    "2026-11-19T12:00:00": False, "2026-11-19T18:00:00+00:00": False,
}


@pytest.mark.parametrize("text, inside", AWARE.items(), ids=repr)
def test_an_aware_interval_admits_the_instants_between_its_bounds_at_any_offset(text, inside):
    lo = dt.datetime(2026, 11, 19, 9, tzinfo=dt.timezone.utc)
    hi = dt.datetime(2026, 11, 19, 17, 30, tzinfo=dt.timezone.utc)
    language = iso_datetime_within(lo, "2026-11-19T18:30:00+01:00")
    assert language.name == ('iso_datetime, within ("2026-11-19T09:00:00+00:00", '
                             '"2026-11-19T18:30:00+01:00")')
    assert language.contains(text) == inside == _datetime_reference(text, lo, hi)


@pytest.mark.parametrize("lo, hi", [
    ("2026-11-19T09:00:00", "2026-11-19T17:30:00"),
    ("2026-11-19T09:00:00+00:00", "2026-11-19T17:30:00+00:00"),
    ("2026-11-19T09:00:00.250000-08:00", "2026-11-19T09:00:00.250000-08:00"),
    ("0001-01-01T00:00:00", "0001-01-01T00:00:01"),
    ("9999-12-31T23:59:58+00:00", "9999-12-31T23:59:59.999999+00:00"),
    ("0001-01-01T00:00:00+00:00", "0001-01-01T12:00:00+00:00"),
], ids=repr)
def test_datetime_draws_are_members_and_the_near_values_are_not(lo, hi):
    language = iso_datetime_within(lo, hi)
    first, last = dt.datetime.fromisoformat(lo), dt.datetime.fromisoformat(hi)
    assert languages.language_problems(language) == []
    rng = random.Random(7)
    texts = [language.sample(rng) for _ in range(100)]
    texts += [h.value for h in language.hazards()]
    texts += [t for t in (language.outside(random.Random(s)) for s in range(100)) if t is not None]
    texts += [ISO_DATETIME.sample(rng) for _ in range(100)]
    for text in texts:
        assert language.contains(text) == _datetime_reference(text, first, last), text
    _draws_hold(language)


def test_a_datetime_draw_beside_the_boundary_is_a_microsecond_out_or_the_other_awareness():
    language = iso_datetime_within("2026-11-19T09:00:00+00:00", "2026-11-19T17:30:00+00:00")
    assert {"2026-11-19T09:00:00+00:00", "2026-11-19T17:30:00+00:00"} <= {h.value for h in language.hazards()}
    assert any(h.value == "2026-11-19T10:00:00+01:00" for h in language.hazards())
    drawn = {language.outside(random.Random(seed)) for seed in range(300)}
    assert {"2026-11-19T08:59:59.999999+00:00", "2026-11-19T17:30:00.000001+00:00",
            "2026-11-19T09:00:00"} <= drawn
    assert within(ISO_DATETIME, "2026-11-19T09:00:00+00:00", "2026-11-19T17:30:00+00:00").name == language.name


@pytest.mark.parametrize("lo, hi", [
    ("2026-11-19T17:30:00", "2026-11-19T09:00:00"), ("2026-11-19T09:00:00", "2026-11-19T17:30:00+00:00"),
    ("2026-11-19T09:00:00", "later"),
])
def test_a_datetime_interval_has_bounds_of_one_awareness_in_order(lo, hi):
    with pytest.raises(ValueError):
        iso_datetime_within(lo, hi)


# --- URLs: an origin, or a path prefix under one


URLS = {
    "https://example.com": True, "https://example.com/": True, "HTTPS://Example.COM/a?b#c": True,
    "http://user:pw@example.com:8080/a": True, "http://a@b@example.com/": True, "x+y.z-1://h": True,
    "http://example.com:65535": True, "http://example.com:00080/": True, "http://127.0.0.1/": True,
    "http://example.com/café": True, "http://example.com/a\\b": True,
    "example.com": False, "//example.com/a": False, "http:/example.com": False, "http://": False,
    "http:///a": False, "http://example.com:": False, "http://example.com:65536": False,
    "http://example.com:8o": False, "http://exa mple.com/": False, "http://example.com/a b": False,
    "http://example.com/\n": False, " http://example.com": False, "http://[::1]/": False,
    "http://example.com\\@evil.example/": False, "http://exämple.com/": False,
    "1http://example.com": False, "http://example.com:080808/": False, "http://user@:80/": False,
    "http://exam_ple.com/": False, "": False,
}


def _url_reference(text: str) -> bool:
    """`L[url]` by `urlsplit`: text with no space or control character
    that splits into a scheme starting with a letter, a `//` authority
    over ASCII with no bracket or backslash, a host of letters, digits,
    hyphens and dots, and a port, when one is written, of one to five
    digits that `urlsplit` reads."""
    if any(ord(c) <= 0x20 for c in text):
        return False
    try:
        parts = urlsplit(text)
        parts.port  # noqa: B018
    except ValueError:
        return False
    head = text[:len(parts.scheme) + 3]
    if not parts.scheme or head.lower() != parts.scheme + "://" or not text[0].isalpha():
        return False
    netloc = parts.netloc
    if not netloc.isascii() or set(netloc) & set("[]\\"):
        return False
    host, colon, port = netloc.rpartition("@")[2].partition(":")
    if re.fullmatch(r"[A-Za-z0-9.-]+", host) is None or parts.hostname != host.lower():
        return False
    return not colon or re.fullmatch(r"[0-9]{1,5}", port) is not None


@pytest.mark.parametrize("text, inside", URLS.items(), ids=repr)
def test_the_url_language_admits_what_urlsplit_reads_one_way(text, inside):
    assert URL.contains(text) == inside == _url_reference(text)
    assert (re.fullmatch(URL_PATTERN, text) is not None) == inside


def test_the_url_language_draws_members_and_agrees_with_its_pattern_on_near_text():
    assert languages.language_problems(URL) == []
    assert URL.name == "url"
    _draws_hold(URL)
    rng = random.Random(8)
    texts = list(URLS) + [URL.sample(rng) for _ in range(200)]
    texts += [m for t in list(texts) for m in _mutations(rng, t, "/:@?#.[]\\ a0%-+", 6)]
    for text in texts:
        assert URL.contains(text) == _url_reference(text), text
        assert (re.fullmatch(URL_PATTERN, text) is not None) == URL.contains(text), text


def _origin(text: str) -> tuple[str, str, int | None] | None:
    """The scheme, host and port `urlsplit` reads from `text`, the port
    the scheme's own when none is written (80 for http, 443 for https),
    or None when the text is no URL or names a user."""
    if not _url_reference(text):
        return None
    parts = urlsplit(text)
    if "@" in parts.netloc:
        return None
    port = parts.port if parts.port is not None else {"http": 80, "https": 443}.get(parts.scheme)
    return parts.scheme, parts.hostname, port


def _url_within_reference(text: str, regions: tuple[str, ...]) -> bool:
    origin = _origin(text)
    if origin is None:
        return False
    path = urlsplit(text).path
    for region in regions:
        if _origin(region) != origin:
            continue
        prefix = urlsplit(region).path.rstrip("/")
        if prefix == "":
            return True
        climbs = any(re.fullmatch(r"(?:\.|%2[eE]){2}", s) for s in path.split("/"))
        if "\\" not in path and not climbs and (path == prefix or path.startswith(prefix + "/")):
            return True
    return False


ORIGIN = {
    "https://example.com": True, "https://example.com/": True, "https://example.com/a/../b?q#f": True,
    "HTTPS://EXAMPLE.com:443/a": True, "https://example.com:0443": True, "https://example.com?q": True,
    "http://example.com/": False, "https://example.com:8443/": False, "https://example.com.evil.example/": False,
    "https://example.computer/": False, "https://user@example.com/": False,
    "https://example.com@evil.example/": False, "https://evil.example/https://example.com": False,
    "https://example.com:80/": False, "https://sub.example.com/": False, "https://example.co": False,
    "https://example.com./": False, "https://example.com\\@evil.example/": False,
}


@pytest.mark.parametrize("text, inside", ORIGIN.items(), ids=repr)
def test_an_origin_admits_the_urls_of_that_scheme_host_and_port_with_no_user(text, inside):
    language = url_within("https://example.com")
    assert language.name == 'url, within ("https://example.com")'
    assert language.contains(text) == inside == _url_within_reference(text, ("https://example.com",))


PREFIX = {
    "https://example.com/api": True, "https://example.com/api/": True, "https://example.com/api/v1/x?q=1#f": True,
    "https://EXAMPLE.com:443/api/v1": True, "https://example.com/api?next=/admin": True,
    "https://example.com/api//v1": True, "https://example.com/api/./v1": True,
    "https://example.com/api/...": True,
    "https://example.com/apiv2": False, "https://example.com/api2/": False, "https://example.com/": False,
    "https://example.com": False, "https://example.com/admin": False, "https://example.com/API": False,
    "https://example.com/api/../admin": False, "https://example.com/api/%2e%2e/admin": False,
    "https://example.com/api/.%2E/admin": False, "https://example.com/api/..": False,
    "https://example.com/api\\..\\admin": False, "https://example.com/api/a\\b": False,
    "https://user@example.com/api": False, "http://example.com/api": False,
    "https://example.com//api": False, "https://example.com/ap": False,
}


@pytest.mark.parametrize("text, inside", PREFIX.items(), ids=repr)
def test_a_prefix_admits_the_urls_at_or_under_that_path_with_no_climb(text, inside):
    language = url_within("https://example.com/api/")
    assert language.name == 'url, within ("https://example.com/api")'
    assert language.contains(text) == inside == _url_within_reference(text, ("https://example.com/api",))


@pytest.mark.parametrize("regions", [
    ("https://example.com",), ("https://example.com/api",), ("http://example.com:8080/a/b",),
    ("https://example.com/api", "https://static.example.com", "http://localhost:3000/"),
    ("ftp://files.example.com/pub",), ("http://example.com:80",), ("https://example.com:0",),
    ("https://example.com/a%20b/c.d",),
], ids=repr)
def test_url_regions_agree_with_urlsplit_and_with_their_pattern(regions):
    language = url_within(*regions)
    assert languages.language_problems(language) == []
    rng = random.Random(9)
    texts = list(ORIGIN) + list(PREFIX) + list(URLS) + list(regions)
    texts += [language.sample(rng) for _ in range(100)] + [h.value for h in language.hazards()]
    texts += [t for t in (language.outside(random.Random(s)) for s in range(100)) if t is not None]
    texts += [r + tail for r in regions for tail in ("/", "/x", "/..", "/%2E%2e/x", "x", "?q", "#f", ":80",
                                                     ":443", ":8080", "/a\\b", ".", "@h", "/x/../y")]
    texts += [m for t in list(texts) for m in _mutations(rng, t, "/:@?#.\\ a0%2eE", 4)]
    for text in texts:
        assert language.contains(text) == _url_within_reference(text, language.regions), text
        assert URL.contains(text) or not language.contains(text)
    _agree(language, texts)
    _draws_hold(language)


def test_a_url_draw_beside_the_boundary_names_a_user_another_port_or_a_longer_host():
    language = url_within("https://example.com/api")
    drawn = {language.outside(random.Random(seed)) for seed in range(400)}
    assert {"https://user@example.com/api", "https://example.com@evil.example/api",
            "https://example.com:8443/api", "https://example.com.evil.example/api",
            "https://example.computer/api", "http://example.com/api", "https://example.com/api/../admin",
            "https://example.com/api/%2e%2e/admin", "https://example.com/apiv2"} <= drawn
    assert within(URL, "https://example.com/api").name == language.name


@pytest.mark.parametrize("region", [
    "example.com", "https://user@example.com", "https://example.com/a?b", "https://example.com/a#b",
    "https://example.com/a/../b", "https://example.com/a\\b", "https://example.com/%2e%2e/a", "",
])
def test_a_url_region_is_a_url_with_no_user_query_fragment_or_climb(region):
    with pytest.raises(ValueError):
        url_within(region)


def test_within_is_refused_on_a_language_with_no_boundary_meaning():
    from mathema_language.text import SLUG
    with pytest.raises(ValueError):
        within(SLUG, "a")
