# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Each predicate language is exactly what its standard-library parser
accepts: a member parses, a non-member does not, and the generator
lands inside a language too narrow for character draws."""
import base64
import datetime as dt
import ipaddress
import json
import random
import shlex
import uuid

import pytest

from mathema_language.text.predicates import (
    BASE64,
    HEX,
    IDENTIFIER,
    IPV4,
    IPV6,
    ISO_DATE,
    ISO_DATETIME,
    JSON,
    SHELL_SAFE,
    SLUG,
    UUID,
)

PREDICATES = [IDENTIFIER, JSON, UUID, ISO_DATE, ISO_DATETIME, IPV4, IPV6,
              BASE64, HEX, SLUG, SHELL_SAFE]


@pytest.mark.parametrize("language", PREDICATES, ids=lambda lang: lang.name)
def test_the_generator_lands_inside(language):
    rng = random.Random(5)
    for _ in range(100):
        assert language.contains(language.sample(rng))


@pytest.mark.parametrize("language,oracle", [
    (JSON, json.loads), (UUID, uuid.UUID), (ISO_DATE, dt.date.fromisoformat),
    (ISO_DATETIME, dt.datetime.fromisoformat), (IPV4, ipaddress.IPv4Address),
    (IPV6, ipaddress.IPv6Address), (HEX, bytes.fromhex),
], ids=lambda item: getattr(item, "name", getattr(item, "__name__", "oracle")))
def test_membership_is_the_oracle_s(language, oracle):
    rng = random.Random(9)
    for _ in range(100):
        member = language.sample(rng)
        oracle(member)
    for _ in range(20):
        value = language.outside(rng)
        if value is None:
            continue
        with pytest.raises(ValueError):
            oracle(value)


def test_json_accepts_what_loads_accepts():
    assert JSON.contains("[1, {\"a\": null}]") and JSON.contains("1e309")
    assert JSON.contains("NaN") and not JSON.contains("") and not JSON.contains("{")


def test_identifier_is_str_isidentifier():
    assert IDENTIFIER.contains("_x1") and IDENTIFIER.contains("été")
    assert not IDENTIFIER.contains("") and not IDENTIFIER.contains("1x")


def test_uuid_accepts_every_spelling_the_parser_does():
    for hazard in UUID.hazards():
        uuid.UUID(hazard.value)
    assert not UUID.contains("not-a-uuid")


def test_base64_is_the_canonical_encoding_only():
    assert BASE64.contains("QQ==") and BASE64.contains("")
    assert not BASE64.contains("QQ=")
    assert base64.b64encode(base64.b64decode("QUE=")).decode() == "QUE="


def test_slug_and_shell_safe():
    assert SLUG.contains("a-b2") and not SLUG.contains("-a") and not SLUG.contains("A")
    assert SHELL_SAFE.contains("a/b.c") and not SHELL_SAFE.contains("") \
        and not SHELL_SAFE.contains("a b")
    assert all(shlex.quote(SHELL_SAFE.sample(random.Random(2))) ==
               SHELL_SAFE.sample(random.Random(2)) for _ in range(3))


def test_time_hazards_parse():
    for hazard in ISO_DATETIME.hazards():
        if hazard.kind == "time":
            dt.datetime.fromisoformat(hazard.value)
    for hazard in ISO_DATE.hazards():
        if hazard.kind == "time":
            dt.date.fromisoformat(hazard.value)
