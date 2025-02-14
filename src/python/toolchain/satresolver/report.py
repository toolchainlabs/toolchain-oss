# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass

from toolchain.satresolver.cause import ConflictCause
from toolchain.satresolver.incompatibility import Incompatibility

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Line:
    message: str
    line_number: int | None


class Report:
    def __init__(self, incompatibility: Incompatibility):
        self.incompatibility = incompatibility
        self.line_numbers: dict[Incompatibility, int] = {}
        self.lines: list[Line] = []
        self.derivations: defaultdict = defaultdict(int)

    def construct_error_message(self) -> list[Line]:
        self.count_derivations(self.incompatibility)
        if isinstance(self.incompatibility.cause, ConflictCause):
            self.visit(self.incompatibility)
        else:
            self._write(self.incompatibility, f"Because {self.incompatibility}, version solving failed.")
        return self.lines

    def _write(self, incompatibility: Incompatibility, message: str, numbered: bool = False) -> None:
        if numbered:
            number = len(self.line_numbers) + 1
            self.line_numbers[incompatibility] = number
            self.lines.append(Line(message, number))
        else:
            self.lines.append(Line(message, None))

    def visit(self, incompatibility: Incompatibility, conclusion: bool = False) -> None:
        numbered = conclusion or self.derivations[incompatibility] > 1
        conjunction = "So," if conclusion or incompatibility == self.incompatibility else "And"
        incompatibility_string = "version solving failed." if incompatibility.is_failure else str(incompatibility)
        cause = incompatibility.cause

        if not isinstance(cause, ConflictCause):
            return
        # Conflict Cause
        if isinstance(cause.conflict.cause, ConflictCause) and isinstance(cause.other.cause, ConflictCause):
            # Both transitive causes are Conflict Causes
            conflict_line = self.line_numbers.get(cause.conflict)
            other_line = self.line_numbers.get(cause.other)

            if conflict_line is not None and other_line is not None:
                # Both transitive causes are in line_numbers already
                self._write(incompatibility, f"Because {cause.conflict}, {incompatibility_string}", numbered=numbered)
            if conflict_line or other_line:
                # One or the other is in line_numbers already
                if other_line is None and conflict_line is not None:
                    with_line = cause.conflict
                    without_line = cause.other
                    line = conflict_line
                elif conflict_line is None and other_line is not None:
                    with_line = cause.other
                    without_line = cause.conflict
                    line = other_line

                self.visit(without_line)
                self._write(
                    incompatibility, f"{conjunction} because {with_line} {line}, {incompatibility}", numbered=numbered
                )
            else:
                if self.is_single_line(cause.other.cause) or self.is_single_line(cause.conflict.cause):
                    # No lines for either
                    self.visit(cause.conflict)
                    self.visit(cause.other)
                    self._write(
                        incompatibility=incompatibility, message=f"Thus, {incompatibility_string}", numbered=numbered
                    )
                else:
                    self.visit(cause.conflict, conclusion=True)
                    self.lines.append(Line("", None))
                    self.visit(cause.other)
                    self._write(
                        incompatibility,
                        f"{conjunction} because {cause.conflict} ({self.line_numbers[cause.conflict]}), {incompatibility_string}",
                    )

        elif isinstance(cause.conflict.cause, ConflictCause) or isinstance(cause.other.cause, ConflictCause):
            # One of the transitive causes is a conflictCause:
            derived: Incompatibility = (
                cause.conflict if isinstance(cause.conflict.cause, ConflictCause) else cause.other
            )
            external = cause.other if isinstance(cause.conflict.cause, ConflictCause) else cause.conflict.cause
            derived_line = self.line_numbers.get(derived)
            if derived_line is not None:
                self._write(incompatibility, f"Because {external} and {derived}, {incompatibility_string}")
            else:
                self.visit(derived)
                self._write(incompatibility, f"{conjunction} because {external}, {incompatibility_string}")
        else:
            # Neither cause is a conflictCause:
            self._write(incompatibility, f"Because {cause.conflict} and {cause.other}, {incompatibility_string}")

    def is_single_line(self, cause: ConflictCause) -> bool:
        return not isinstance(cause.conflict.cause, ConflictCause) and not isinstance(cause.other.cause, ConflictCause)

    def count_derivations(self, incompatibility: Incompatibility) -> None:
        if incompatibility not in self.derivations:
            cause = incompatibility.cause
            if isinstance(cause, ConflictCause):
                self.count_derivations(cause.conflict)
                self.count_derivations(cause.other)
        self.derivations[incompatibility] += 1
