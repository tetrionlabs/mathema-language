# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""Comment threads, where every comment holds its replies."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Comment:
    author: str
    body: str
    replies: list[Comment] = field(default_factory=list)


def thread_size(comment: Comment) -> int:
    """How many comments the thread holds, this one included."""
    return 1 + sum(thread_size(r) for r in comment.replies)


def replies_below(comment: Comment) -> int:
    """How many replies sit under this comment, at any depth."""
    return len(comment.replies) + sum(replies_below(r) for r in comment.replies)


def thread_depth(comment: Comment) -> int:
    """How many levels the thread has, this comment's included."""
    return 1 + max((thread_depth(r) for r in comment.replies), default=0)
