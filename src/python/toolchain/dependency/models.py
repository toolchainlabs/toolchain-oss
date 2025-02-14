# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import hashlib
import itertools
import json
import logging
from collections.abc import Collection, Iterable, Mapping
from enum import Enum, unique
from typing import Union

import shortuuid
from django.db.models import CharField, DateTimeField, IntegerField, JSONField, TextField

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion, ToolchainError
from toolchain.dependency.constants import ErrorType, SolutionResult, SolutionStatus
from toolchain.django.db.base_models import ToolchainModel
from toolchain.django.db.transaction_broker import TransactionBroker
from toolchain.workflow.models import WorkUnitPayload

transaction = TransactionBroker("dependency")
_logger = logging.getLogger(__name__)

ResolverParameters = Mapping[str, Union[str, Collection[str]]]


class MissingSolutionObject(ToolchainError):
    """Raised when we can't find a ResolverSolution row for a given solution_id."""


@unique
class SolutionState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    FINISHED = "finished"


class ResolverSolution(ToolchainModel):
    State = SolutionState
    id = CharField(max_length=22, default=shortuuid.uuid, primary_key=True, db_index=True, editable=False)
    created_at = DateTimeField(default=utcnow, editable=False)
    last_update = DateTimeField(null=True)
    leveldb_version = IntegerField(editable=False)
    dependencies_digest = CharField(editable=False, max_length=64)
    parameters_digest = CharField(editable=False, max_length=64)
    _solution_state = CharField(max_length=10, default=SolutionState.PENDING.value, db_column="state")
    _error_type = CharField(max_length=24, default="", db_column="error_type")
    _result = TextField(max_length=8192)

    @classmethod
    def get_or_create(
        cls,
        *,
        dependencies: list[str],
        parameters: ResolverParameters,
        leveldb_version: int,
        dispatch_async: bool = True,
    ) -> SolutionResult:
        def _get_hash(data: Iterable[str]):
            return hashlib.sha256(json.dumps(sorted(data)).encode()).hexdigest()

        def _normalize_value(value):
            return value if isinstance(value, str) else "-".join(sorted(value))

        dependencies_digest = _get_hash(dependencies)
        normalized_params = {key: _normalize_value(value) for key, value in parameters.items()}
        parameters_digest = _get_hash(itertools.chain(*normalized_params.items()))
        obj, created = cls.objects.get_or_create(
            dependencies_digest=dependencies_digest,
            parameters_digest=parameters_digest,
            leveldb_version=leveldb_version,
        )
        if created and dispatch_async:
            # Queue up workflow resolve work.
            ResolveDependencies.create_for_solution(
                solution_id=obj.id, requirements=dependencies, parameters=parameters
            )
        return obj.to_result()

    @classmethod
    def get_by_id(cls, solution_id: str) -> ResolverSolution | None:
        return cls.get_or_none(id=solution_id)

    @classmethod
    def store_solution(cls, solution_id: str, solution: dict, error_type: ErrorType | None = None) -> SolutionResult:
        solution_str = json.dumps(solution)
        # TODO: check size, blow up if it is to big.
        # report the size to metric
        with transaction.atomic():
            rs = cls.objects.select_for_update().filter(id=solution_id).first()
            if not rs:
                raise MissingSolutionObject(f"No solution found for: {solution_id}")
            rs._save_solution(solution_str=solution_str, error_type=error_type)
        return rs.to_result()

    @classmethod
    def clean_old_solutions(cls, threshold: datetime.datetime) -> int:
        deleted, _ = cls.objects.filter(created_at__lt=threshold).delete()
        return deleted

    def _save_solution(self, solution_str: str, error_type: ErrorType | None) -> bool:
        if self.is_completed:
            _logger.info("Already have a solution for {self}")
            return False
        self.last_update = utcnow()
        self._error_type = error_type.value if error_type is not None else ""
        self._result = solution_str
        self._solution_state = self.State.FINISHED.value
        self.save()
        return True

    def to_result(self) -> SolutionResult:
        if not self.is_completed:
            return SolutionResult.pending(solution_id=self.id, db_version=self.leveldb_version)
        error_type = self.error_type
        status = SolutionStatus.FAIL if error_type else SolutionStatus.SUCCESS
        return SolutionResult(
            solution_id=self.id,
            db_version=self.leveldb_version,
            status=status,
            error_type=error_type,
            result=json.loads(self._result),
        )

    @property
    def error_type(self) -> ErrorType | None:
        return ErrorType(self._error_type) if self._error_type else None

    @property
    def state(self) -> SolutionState:
        return SolutionState(self._solution_state)

    @property
    def is_completed(self) -> bool:
        return self.state == SolutionState.FINISHED

    def __str__(self):
        return f"Solution(solution_id={self.id} leveldb_version={self.leveldb_version} state={self._solution_state})"


class PeriodicallyCleanOldSolutions(WorkUnitPayload):
    # Check changelog every this many minutes (or None for one-time processing).
    # Trigger a job to delete old ResolverSolution rows.
    period_minutes = IntegerField(null=True)
    threshold_days = IntegerField()

    @classmethod
    def create_or_update(cls, period_minutes: int, threshold_days: int):
        if cls.objects.count() > 1:
            raise ToolchainAssertion("More than one PeriodicallyProcessChangelog objects is not supported.")
        with transaction.atomic():
            pcos = cls.objects.first() or cls()
            pcos.period_minutes = period_minutes
            pcos.threshold_days = threshold_days
            pcos.save()


class CleanOldSolutions(WorkUnitPayload):
    threshold = DateTimeField()  # Solution created before threshold will be removed

    @classmethod
    def create(cls, threshold: datetime.datetime) -> CleanOldSolutions:
        return cls.objects.create(threshold=threshold)


class ResolveDependencies(WorkUnitPayload):
    solution_id = CharField(max_length=22, editable=False)
    python_requirements = JSONField()
    parameters = JSONField()

    @classmethod
    def create_for_solution(
        cls, solution_id: str, requirements: list[str], parameters: ResolverParameters
    ) -> ResolveDependencies:
        return cls.objects.create(solution_id=solution_id, python_requirements=requirements, parameters=parameters)
