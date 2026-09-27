# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""The structure of a JSON text read straight off the text, without
parsing it into Python values: depth, nodes, children and leaves as
`vocabulary.tree` defines them for the parsed value. The scan is one
pass with an explicit stack, so a document nested far past the
interpreter's recursion limit (where `json.loads` raises
RecursionError) is measured all the same. The text is assumed to be
JSON; membership in `L[json]` is decided separately."""
from __future__ import annotations

_LITERAL_START = set("-0123456789tfn")
_LITERAL_BODY = set("0123456789+-.eEtruefalsn")


def scan(text: str) -> tuple[int, int, int, int]:
    """(depth, nodes, children, leaves) of the JSON value `text`
    denotes."""
    max_depth = nodes = widest = leaves = 0
    # per open container: [element count, is object, expecting a key]
    stack: list[list[int | bool]] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            is_key = bool(stack) and stack[-1][1] and stack[-1][2]
            if not is_key:
                nodes += 1
                leaves += 1
                max_depth = max(max_depth, len(stack))
                if stack:
                    stack[-1][0] += 1
            i = j + 1
            continue
        if c in "[{":
            nodes += 1
            if stack:
                stack[-1][0] += 1
            stack.append([0, c == "{", c == "{"])
            max_depth = max(max_depth, len(stack))
            i += 1
            continue
        if c in "]}":
            count = stack.pop()[0]
            widest = max(widest, count)
            if count == 0:
                leaves += 1
            i += 1
            continue
        if c == ":":
            if stack:
                stack[-1][2] = False
            i += 1
            continue
        if c == ",":
            if stack and stack[-1][1]:
                stack[-1][2] = True
            i += 1
            continue
        if c in _LITERAL_START:
            j = i + 1
            while j < n and text[j] in _LITERAL_BODY:
                j += 1
            nodes += 1
            leaves += 1
            max_depth = max(max_depth, len(stack))
            if stack:
                stack[-1][0] += 1
            i = j
            continue
        i += 1
    return max_depth, nodes, widest, leaves


__all__ = ["scan"]
