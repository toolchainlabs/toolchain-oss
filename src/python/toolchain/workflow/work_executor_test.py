# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

import pytest

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.workflow.constants import WorkExceptionCategory
from toolchain.workflow.error import TransientWorkException
from toolchain.workflow.models import WorkExceptionLog, WorkUnit, WorkUnitPayload
from toolchain.workflow.work_dispatcher_test import FibCompute, FibComputer
from toolchain.workflow.work_executor import WorkExecutor
from toolchain.workflow.worker import Worker


class BadFibComputerWorker(Worker):
    work_unit_payload_cls = FibCompute

    def __init__(self, category: WorkExceptionCategory | None, delay_sec: int | None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._category = category
        self._delay = datetime.timedelta(seconds=delay_sec) if delay_sec else None

    def do_work(self, work_unit_payload):
        # Since classify_error is implemented, the category on the exception should be ignored.
        raise TransientWorkException("No soup for you")

    def classify_error(self, exception: Exception) -> WorkExceptionCategory | None:
        return self._category

    def transient_error_retry_delay(
        self, work_unit_payload: WorkUnitPayload, exception: Exception
    ) -> datetime.timedelta | None:
        return self._delay


@pytest.mark.django_db(transaction=True)
class TestWorkExecutor:
    def _get_bad_executer(self, worker: BadFibComputerWorker) -> WorkExecutor:
        payload = FibCompute.objects.create(index=5)
        now = utcnow()
        wu = payload.work_unit
        wu.take_lease(until=now + datetime.timedelta(minutes=3), last_attempt=now, node="test")
        wu.refresh_from_db()
        return WorkExecutor(wu, worker, context={})

    def _get_executor(self, fib_num: int, error_type=ToolchainAssertion) -> WorkExecutor:
        worker = FibComputer(error_type=error_type)
        payload = FibCompute.objects.create(index=fib_num)
        now = utcnow()
        wu = payload.work_unit
        wu.take_lease(until=now + datetime.timedelta(minutes=3), last_attempt=now, node="test")
        wu.refresh_from_db()
        return WorkExecutor(wu, worker, context={})

    def test_execute_success(self) -> None:
        executor = self._get_executor(1)
        wu = executor.work_unit
        executor.execute()
        wu.refresh_from_db()
        assert wu.state == WorkUnit.SUCCEEDED
        assert WorkExceptionLog.objects.count() == 0

    def test_execute_fail_with_reschedule(self) -> None:
        executor = self._get_executor(5)
        wu = executor.work_unit
        executor.execute()
        wu.refresh_from_db()
        assert wu.state == WorkUnit.PENDING
        assert WorkExceptionLog.objects.count() == 0

    def test_execute_failure(self) -> None:
        assert WorkExceptionLog.objects.count() == 0
        executor = self._get_executor(-10)
        wu = executor.work_unit
        executor.execute()
        wu.refresh_from_db()
        assert wu.state == WorkUnit.INFEASIBLE
        assert WorkExceptionLog.objects.count() == 1
        exception_log = WorkExceptionLog.objects.first()
        assert exception_log.category == "PERMANENT"
        assert exception_log.work_unit_id == wu.id
        assert exception_log.work_unit == wu
        assert exception_log.message == "No soup for you"
        assert "raise self._error_type(" in exception_log.stacktrace

    def test_release(self) -> None:
        executor = self._get_executor(5)
        wu = executor.work_unit
        executor.release()
        wu.refresh_from_db()
        assert wu.state == WorkUnit.READY
        assert WorkExceptionLog.objects.count() == 0

    def test_default_error_transient_error(self) -> None:
        worker = BadFibComputerWorker(None, None)
        executor = self._get_bad_executer(worker)
        wu = executor.work_unit
        executor.execute()
        wu.refresh_from_db()
        assert wu.state == WorkUnit.LEASED
        assert wu.leased_until is None
        assert WorkExceptionLog.objects.count() == 1

    def test_advisory_error(self) -> None:
        worker = BadFibComputerWorker(WorkExceptionCategory.ADVISORY, 180)
        executor = self._get_bad_executer(worker)
        wu = executor.work_unit
        executor.execute()
        wu.refresh_from_db()
        assert wu.state == WorkUnit.SUCCEEDED
        assert WorkExceptionLog.objects.count() == 1

    def test_permanent_error(self) -> None:
        worker = BadFibComputerWorker(WorkExceptionCategory.PERMANENT, 180)
        executor = self._get_bad_executer(worker)
        wu = executor.work_unit
        executor.execute()
        wu.refresh_from_db()
        assert wu.state == WorkUnit.INFEASIBLE
        assert WorkExceptionLog.objects.count() == 1

    def test_transient_error_with_delay(self) -> None:
        worker = BadFibComputerWorker(WorkExceptionCategory.TRANSIENT, 55)
        executor = self._get_bad_executer(worker)
        wu = executor.work_unit
        executor.execute()
        wu.refresh_from_db()
        assert wu.state == WorkUnit.LEASED
        assert (utcnow() + datetime.timedelta(seconds=55)).timestamp() == pytest.approx(wu.leased_until.timestamp())
        assert WorkExceptionLog.objects.count() == 1
