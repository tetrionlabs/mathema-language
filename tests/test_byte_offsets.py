# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The hazard corpus carries long runs of multi-byte characters at odd
byte offsets (`"a" + "é" * n`, `"a" + "日" * n`, `"a" + "😀" * n`),
sized so a cut at a common byte limit (24, 64, 255, 256) lands inside a
character, and `vocabulary.text.utf8_len` counts UTF-8 bytes. So a
truncation by bytes is caught splitting a character, and the safe
version, stated through `utf8_len`, holds."""
import pytest

pytest.importorskip("mathema")

from mathema.conjecture import check_conjectures, claim  # noqa: E402

from mathema_language.text import UNICODE  # noqa: E402
from mathema_language.vocabulary import text  # noqa: E402


def cut_bytes(s: str) -> str:
    """The first 24 bytes of s's UTF-8 form, decoded."""
    return s.encode("utf-8")[:24].decode("utf-8")


def cut_safely(s: str) -> str:
    """At most 24 bytes of s's UTF-8 form, cut at a character boundary."""
    return s.encode("utf-8")[:24].decode("utf-8", "ignore")


def test_the_runs_are_hazards_and_split_a_character_at_each_limit():
    runs = [h.value for h in UNICODE.hazards() if h.kind == "encoding" and h.value.startswith("a")
            and len(set(h.value[1:])) == 1 and len(h.value.encode("utf-8")) > len(h.value)]
    for ch in ("é", "日", "\U0001f600"):
        assert any(r[1] == ch for r in runs), ch
    for limit in (24, 64, 255, 256):
        assert any(len(r.encode("utf-8")) > limit and _splits(r, limit) for r in runs), limit


def _splits(s: str, limit: int) -> bool:
    try:
        s.encode("utf-8")[:limit].decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def test_utf8_len_counts_bytes_and_carries_its_id():
    assert text.utf8_len("aé日\U0001f600") == 1 + 2 + 3 + 4
    assert text.utf8_len.__mathema_vocabulary__ == "text.utf8_len@1"
    assert "utf8_len" in text.__all__


def test_a_byte_cut_is_caught_splitting_a_character():
    (p,) = check_conjectures(cut_bytes, [claim("for s in L[printable], is_encoding_safe(s)")])
    assert p.verdict == "falsified", (p.verdict, p.note)
    assert "UnicodeDecodeError" in p.counterexample, p.counterexample


def test_the_safe_cut_holds_within_its_byte_budget():
    (p,) = check_conjectures(cut_safely, [claim(
        "let n = mathema_language.vocabulary.text.utf8_len, "
        "for s in L[printable], n(f(s)) <= 24")])
    assert p.verdict == "holds", (p.verdict, p.note, p.counterexample)
