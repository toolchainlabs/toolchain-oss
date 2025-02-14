# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, unique


@dataclass
class PythonResolveRequest:
    dependencies: list[str]
    python: str
    platform: str
    abis: set[str]

    def get_parameters(self) -> dict:
        return {
            "python": self.python,
            "platform": self.platform,
            "abis": sorted(self.abis),
        }


@unique
class SolutionStatus(Enum):
    SUCCESS = "success"
    FAIL = "fail"
    UNKNOWN = "unknown"


@unique
class ErrorType(Enum):
    PACKAGE_NOT_FOUND = "package_not_found"
    NO_SOLUTION = "no_solution"
    INVALID_REQUIREMENT = "invalid_requirement"


@dataclass(frozen=True)
class SolutionResult:
    solution_id: str
    db_version: int
    status: SolutionStatus
    result: dict
    error_type: ErrorType | None = None

    @classmethod
    def pending(cls, solution_id, db_version):
        return cls(
            solution_id=solution_id, db_version=db_version, status=SolutionStatus.UNKNOWN, error_type=None, result={}
        )

    @property
    def is_completed(self) -> bool:
        return self.status in {SolutionStatus.FAIL, SolutionStatus.SUCCESS}
