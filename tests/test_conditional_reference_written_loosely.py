# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A conditional group reference written with a sign or a space,
`(?(+1)b|c)`, `(?( 1)b|c)` or `(?(1 )b|c)`, compiles on Python 3.10 and
3.11, which read the number with `int`, and is refused from 3.12, which
takes only ASCII digits. On 3.10 or 3.11 a term for 3.12 and later, or
for every supported Python, is refused. On 3.12 and later the pattern
does not compile, so each case is refused there too."""
import pytest

from mathema_language.text import _regular


@pytest.mark.parametrize("pattern", ["(a)?(?(+1)b|c)", "(a)?(?( 1)b|c)", "(a)?(?(1 )b|c)"])
@pytest.mark.parametrize("version", ["3.12", "3.13", "3.14", None])
def test_a_loosely_written_group_reference_is_refused_for_a_python_that_refuses_it(pattern, version):
    with pytest.raises((_regular.NotRegular, ValueError)):
        _regular.term(pattern, 0, "matches", version=version)
