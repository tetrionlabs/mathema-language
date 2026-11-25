# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The regex delta table rebuilt on the running interpreter matches the
checked-in table for this Python: every construct listed as read alike
reads here with the digest the table records for it, and every
construct with rows reads here as this version's row says. Each hosted
Python lane so checks its own version's part of the table."""
import json
import sys

import pytest

from mathema_language.text import _regular
from tests import _fuzz
from tests import _regex_delta_data as generator

HERE = f"{sys.version_info[0]}.{sys.version_info[1]}"


def test_the_table_rebuilt_here_is_the_checked_in_table_for_this_python(tmp_path):
    table = _regular.regex_deltas()
    if HERE not in table["versions"]:
        pytest.skip(f"python {HERE} is not a supported version")
    path = tmp_path / "here.json"
    generator.dump(str(path))
    readings = json.loads(path.read_text())["readings"]
    rows = {(r["construct"], r["version"]): r for r in table["rows"]}
    for construct, reading in readings.items():
        if construct in table["read_alike"]:
            assert reading["digest"] == table["alike_digests"][construct], construct
        else:
            row = rows[(construct, HERE)]
            reads = "all" if reading["reads"] else "none" if reading["refuses"] else "some"
            assert (row["digest"], row["reads"]) == (reading["digest"], reads), construct
    _fuzz.report("regex delta table", 0, constructs=len(readings), version=int(HERE.split(".")[1]))
