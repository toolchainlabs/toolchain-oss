# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from functools import total_ordering

from toolchain.satresolver.cause import Cause
from toolchain.satresolver.term import Term


@total_ordering
class Assignment(Term):
    """A term in a PartialSolution that tracks some additional metadata."""

    def __init__(self, term: Term, decision_level: int, index: int, cause: Cause | None = None) -> None:
        self.term = term
        self.decision_level = decision_level
        self.index = index
        self.cause = cause

    def __lt__(self, other) -> bool:
        if not isinstance(other, Assignment):
            return NotImplemented
        return self.index < other.index

    def __eq__(self, other) -> bool:
        if not isinstance(other, Assignment):
            return NotImplemented
        return (
            self.term == other.term
            and self.decision_level == other.decision_level
            and self.index == other.index
            and self.cause == other.cause
        )

    def __repr__(self) -> str:
        cause_str = f", {self.cause}" if self.cause else ""
        return f"{self.__class__.__name__}({self.term}, {self.decision_level}, {self.index}{cause_str})"

    def __str__(self) -> str:
        return str(self.term)

    @property
    def is_decision(self) -> bool:
        return self.cause is None

    @property
    def subject(self) -> str:
        return self.term.subject
