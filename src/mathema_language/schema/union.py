# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Tetrion Ltd
"""A union of record languages: a value is a member when it is a member
of one branch, and the branch is the one whose fixed fields it carries
(a command line's subcommand, a message's `type`). Every operation
delegates to the branches: a draw picks a branch and draws inside it,
the hazards visit every branch in turn, and the fields the derive lift
reads are those the branches agree on."""
from __future__ import annotations

import random
from collections.abc import Iterable
from typing import Any

from .._surface import HazardValue, Problem
from .languages import RowLanguage


class UnionLanguage:
    """The union of `branches`, each a `RowLanguage`. `pick` returns the
    branch a value belongs to, or None when it belongs to none."""

    kind = "row"
    level = "schema"

    def __init__(self, name: str, branches: tuple[RowLanguage, ...],
                 pick: Any) -> None:
        if not branches:
            raise ValueError(f"{name}: a union needs at least one branch")
        self.name = name
        self.branches = branches
        self.pick = pick

    def __repr__(self) -> str:
        return f"UnionLanguage({self.name!r}, {len(self.branches)} branches)"

    def _branch(self, value: Any) -> RowLanguage | None:
        """Intent:
            Returns the branch `pick` assigns a value to, or None when it belongs to none.
        """
        index = self.pick(value)
        return self.branches[index] if index is not None else None

    def explain(self, value: Any) -> list[Problem] | None:
        branch = self._branch(value)
        if branch is None:
            return [Problem("", f"one of the {len(self.branches)} shapes of {self.name}", value)]
        return branch.explain(value)

    def contains(self, value: Any) -> bool:
        return self.explain(value) is None

    def sample(self, rng: random.Random) -> Any:
        return rng.choice(self.branches).sample(rng)

    def members(self, limit: int) -> tuple[Any, ...] | None:
        out: list[Any] = []
        for branch in self.branches:
            found = branch.members(limit - len(out))
            if found is None:
                return None
            out.extend(found)
        return tuple(out)

    def hazards(self) -> tuple[HazardValue, ...]:
        """Each branch's hazards, taken in turn, so every shape is met
        early."""
        queues = [list(branch.hazards()) for branch in self.branches]
        out: list[HazardValue] = []
        while any(queues):
            for queue in queues:
                if queue:
                    out.append(queue.pop(0))
        return tuple(out)

    def outside(self, rng: random.Random) -> Any:
        order = list(self.branches)
        rng.shuffle(order)
        for branch in order:
            value = branch.outside(rng)
            if value is not None and not self.contains(value):
                return value
        return None

    def shrink(self, value: Any) -> Iterable[Any]:
        branch = self._branch(value)
        return branch.shrink(value) if branch is not None else ()

    def fields(self) -> dict[str, Any] | None:
        """The fields every branch has with the same bound."""
        per_branch = [branch.fields() or {} for branch in self.branches]
        common = set(per_branch[0]).intersection(*per_branch[1:])
        return {name: per_branch[0][name] for name in sorted(common)
                if all(repr(b[name]) == repr(per_branch[0][name]) for b in per_branch)}

    def render(self, ascii_mode: bool = True) -> str:
        return f"L[{self.name}]"

    def to_json(self) -> dict[str, Any]:
        return {"anyOf": [branch.to_json() for branch in self.branches]}


__all__ = ["UnionLanguage"]
