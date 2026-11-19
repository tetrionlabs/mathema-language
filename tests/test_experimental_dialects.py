# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A dialect that is not available yet is refused unless the environment
names it as experimental, and nothing the package offers loads its
compiler without that."""
import os
import subprocess
import sys

import pytest

from mathema_language.text import _regular as rx

SWITCH = "MATHEMA_LANGUAGE_EXPERIMENTAL_DIALECTS"


def test_the_dialect_is_refused_without_the_switch(monkeypatch):
    monkeypatch.delenv(SWITCH, raising=False)
    with pytest.raises(rx.NotRegular, match="the javascript dialect is not available yet"):
        rx.term("a", "", "matches", "javascript")
    monkeypatch.setenv(SWITCH, "rust")
    with pytest.raises(rx.NotRegular, match="the javascript dialect is not available yet"):
        rx.term("a", "", "matches", "javascript")
    assert "javascript" not in rx.DIALECTS


@pytest.mark.experimental_dialect
def test_the_switch_is_read_at_each_call(monkeypatch):
    monkeypatch.setenv(SWITCH, "javascript")
    assert rx.term("a", "", "matches", "javascript")["source"]["dialect"] == "javascript"
    monkeypatch.setenv(SWITCH, "")
    with pytest.raises(rx.NotRegular, match="not available yet"):
        rx.term("a", "", "matches", "javascript")


def test_nothing_reaches_the_compiler_without_the_switch():
    script = """
import re, sys
import mathema_language
from mathema_language import smt, refinements
from mathema_language.text import LANGUAGES, UNICODE, adapt, pattern_language, _regular as rx
rx.term(r"\\\\w+$", re.I, "contains")
rx.term(r"a", 0, "matches", version="3.12")
pattern_language(re.compile("a+").search).contains("xa")
adapt(str); adapt(re.compile("a"))
UNICODE.to_json(); [lang.to_json() for lang in LANGUAGES.values()]
try:
    rx.term("a", "", "matches", "javascript")
except rx.NotRegular as e:
    assert "not available yet" in str(e)
else:
    raise SystemExit("the dialect was not refused")
loaded = [m for m in sys.modules if "_ecma" in m or "javascript" in m]
assert not loaded, loaded
print("clean")
"""
    env = {k: v for k, v in os.environ.items() if k != SWITCH}
    done = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env)
    assert done.returncode == 0 and done.stdout.strip() == "clean", done.stderr[-800:]
