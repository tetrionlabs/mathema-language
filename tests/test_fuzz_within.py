# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""`within` over addresses and paths, fuzzed. For IPv4 and IPv6 blocks,
on addresses in and around each block, in every spelling and with small
mutations, the language's own test, its pattern read in full and its
term agree; draws are members and outside values are not. For paths,
over roots with doubled slashes, dot segments, spaces, newlines and
names beside system directories, no draw, hazard or outside value names
a system directory, no draw or hazard climbs out of the roots, and every
draw and hazard is a member of the language and of its term. Seeded; a
small budget by default, the full one under `heavy`."""
import ipaddress
import posixpath
import random
import re

from mathema_language.text import _algebra
from mathema_language.text.path_language import SYSTEM_DIRECTORIES, path_within
from mathema_language.text.within import ipv4_within, ipv6_within
from tests import _fuzz

SEED = 5
BLOCKS4 = ["0.0.0.0/0", "10.0.0.0/8", "192.168.1.128/25", "255.255.255.255/32", "0.0.0.0/32", "127.0.0.0/31",
           "10.0.0.0/8|172.16.0.0/12"]
BLOCKS6 = ["::/0", "2001:db8::/32", "::1/128", "::/128", "fe80::/10", "::ffff:0:0/96",
           "ffff:ffff:ffff:ffff:ffff:ffff:ffff:ff00/120", "2001:db8::/32|::/127", "0:0:0:0:0:1::/96"]
ROOTS = ["/", "//", "/workspace", "/workspace/", "/w/./x", "//etcd", "//tmpx", "/etcd", "/usr2", "/a b", "/é",
         "/x/", "/Usersx", "/privatex", "/varx", "/a\nb"]


def _mutated(rng: random.Random, text: str) -> str:
    chars = list(text)
    for _ in range(rng.randint(0, 2)):
        roll, at = rng.random(), rng.randint(0, len(chars))
        ch = rng.choice("0123456789abcdefABCDEF:.%/ \n١٠e")
        if roll < 0.4 and chars:
            chars[min(at, len(chars) - 1)] = ch
        elif roll < 0.7:
            chars.insert(at, ch)
        elif chars:
            del chars[min(at, len(chars) - 1)]
    return "".join(chars)


def _check_addresses(per_block: int) -> int:
    rng = random.Random(SEED)
    checked = 0
    cases = [(b, ipv4_within, ipaddress.IPv4Address) for b in BLOCKS4]
    cases += [(b, ipv6_within, ipaddress.IPv6Address) for b in BLOCKS6]
    for spec, build, address in cases:
        language = build(*spec.split("|"))
        term, pattern = language.term(), language.pattern
        nets = [ipaddress.ip_network(b) for b in spec.split("|")]
        texts: set[str] = set()
        for _ in range(per_block):
            net = rng.choice(nets)
            value = rng.randint(int(net.network_address), int(net.broadcast_address)) + rng.choice([0, 0, 0, 1, -1])
            value = max(0, min(value, 2 ** net.max_prefixlen - 1))
            spelled = address(value)
            forms = [str(spelled)]
            if address is ipaddress.IPv6Address:
                forms += [spelled.exploded, spelled.exploded.upper(), f"{spelled}%x", f"{spelled}%\n",
                          f"{spelled}% ", f"{spelled}%1%2",
                          ":".join(spelled.exploded.split(":")[:6]) + ":" + str(ipaddress.IPv4Address(value & 0xffffffff))]
            texts |= set(forms) | {_mutated(rng, f) for f in forms}
        texts |= {language.sample(rng) for _ in range(per_block // 6)} | {h.value for h in language.hazards()}
        for text in texts:
            checked += 1
            own, read = language.contains(text), re.fullmatch(pattern, text, re.DOTALL) is not None
            assert own == read == _algebra.member(term, text), (spec, text)
        assert all(language.contains(language.sample(rng)) for _ in range(per_block // 3)), spec
        outside = [language.outside(rng) for _ in range(20)]
        assert not [o for o in outside if o is not None and language.contains(o)], spec
    return checked


def _system(path: str) -> bool:
    if not path.startswith("/"):
        return False
    segments = ("/" + posixpath.normpath(path).lstrip("/")).split("/")[1:]
    return bool(segments) and segments[0] in SYSTEM_DIRECTORIES


def _climbs(path: str, roots: list[str]) -> bool:
    if not path.startswith("/"):
        return ".." in path.split("/")
    normal = "/" + posixpath.normpath(path).lstrip("/")
    for root in roots:
        under = "/" if root.strip("/") == "" else "/" + posixpath.normpath(root).lstrip("/")
        if under == "/" or normal == under or normal.startswith(under + "/"):
            return False
    return True


def _check_paths(draws: int) -> int:
    rng = random.Random(SEED)
    checked = 0
    for root in ROOTS:
        for spec in ([root], [root, "/data"]):
            language = path_within(*spec)
            term = language.term()
            drawn = [language.sample(rng) for _ in range(draws)]
            outside = [language.outside(rng) for _ in range(draws // 6)]
            hazards = [h.value for h in language.hazards()]
            for kind, values in (("draw", drawn), ("outside", outside), ("hazard", hazards)):
                for value in set(values):
                    if value is None:
                        continue
                    checked += 1
                    assert not _system(value), (kind, spec, value)
                    if kind != "outside":
                        assert not _climbs(value, spec), (kind, spec, value)
            for value in set(drawn + hazards):
                assert language.contains(value) and _algebra.member(term, value), (spec, value)
    return checked


def test_addresses_agree_three_ways():
    checked = _check_addresses(60)
    _fuzz.report("within addresses", SEED, texts=checked)


def test_paths_never_offer_a_system_place_or_a_climb():
    checked = _check_paths(20)
    _fuzz.report("within paths", SEED, values=checked)


@_fuzz.heavy
def test_addresses_agree_three_ways_at_full_size():
    checked = _check_addresses(600)
    _fuzz.report("within addresses, full", SEED, texts=checked)


@_fuzz.heavy
def test_paths_never_offer_a_system_place_or_a_climb_at_full_size():
    checked = _check_paths(300)
    _fuzz.report("within paths, full", SEED, values=checked)
