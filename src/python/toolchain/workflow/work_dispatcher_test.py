# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
import time
from queue import Queue
from threading import Thread

import pytest
from django.db.models import IntegerField

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.db.base_models import ToolchainModel
from toolchain.workflow.models import WorkExceptionLog, WorkUnit, WorkUnitPayload
from toolchain.workflow.work_dispatcher import WorkDispatcher, join_queue
from toolchain.workflow.worker import Worker

# Models used in the test below.  Must be defined at the top level, so that
# pytest-django sees them in time to create their tables before entering the test.


def mark_work_unit_success(payload: WorkUnitPayload, rerun_requirers: bool = True) -> WorkUnit:
    work_unit = payload.work_unit
    now = utcnow()
    work_unit.take_lease(until=now + datetime.timedelta(hours=1), last_attempt=now, node="bosco")
    work_unit.work_succeeded(rerun_requirers=rerun_requirers)
    return work_unit


class DispatcherForTests(WorkDispatcher):
    @classmethod
    def for_dispatcher_test(cls, batch_size, worker_cls: type[Worker]):
        WorkDispatcher.singleton = None
        return cls(
            num_executor_threads=0,
            batch_size=batch_size,
            node="test",
            work_payload_types=[worker_cls.work_unit_payload_cls],  # type: ignore
            worker_classes=(worker_cls,),
            worker_calls_log_level=logging.INFO,
        )

    def _process_one_work_batch(self) -> int:
        executors = self._fetch_one_work_batch()
        for executor in executors:
            executor.execute()
        return len(executors)


# A model representing the i'th Fibonacci number, F(i).
class Fib(ToolchainModel):
    index = IntegerField(unique=True, db_index=True)  # Index into the Fibonacci sequence.
    value = IntegerField()  # The value of the index'th Fibonacci number.

    def __str__(self):
        return f"{self.__class__.__name__}(F{self.index}={self.value})"


# The work of computing F(i).
class FibCompute(WorkUnitPayload):
    index = IntegerField(unique=True, db_index=True)

    def __str__(self):
        return f"{self.__class__.__name__}({self.index})"


class DummyPayload(WorkUnitPayload):
    pass


class FibComputer(Worker):
    DEFAULT_LEASE_SECS = 0.1
    work_unit_payload_cls = FibCompute

    def __init__(self, *args, error_type=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._n = None
        self._error_type = error_type

    def do_work(self, work_unit_payload):
        i = work_unit_payload.index
        if i < 0:
            raise self._error_type("No soup for you")
        if i == 0:
            self._n = 0
        elif i == 1:
            self._n = 1
        else:
            try:
                self._n = Fib.objects.get(index=i - 1).value + Fib.objects.get(index=i - 2).value
            except Fib.DoesNotExist:
                return False  # Reschedule.
        return True

    def on_reschedule(self, work_unit_payload):
        i = work_unit_payload.index

        def require(j):
            compute_j, _ = FibCompute.objects.get_or_create(index=j)
            work_unit_payload.add_requirement_by_id(compute_j.work_unit_id)

        require(i - 1)
        require(i - 2)

    def on_success(self, work_unit_payload):
        # Note that verifies, in passing, that we only computed F(i) once for each i.
        # Otherwise create will fail due to the unique constraint on index.
        Fib.objects.create(index=work_unit_payload.index, value=self._n)


@pytest.mark.django_db(transaction=True)
class TestWorkDispatcher:
    def test_work_cycle(self):
        # Test a cycle of work that creates other work, with multiple requirements on the
        # same work, via a laborious way of computing the Fibonacci sequence...
        dispatcher = DispatcherForTests.for_dispatcher_test(batch_size=0, worker_cls=FibComputer)

        # Seed.
        m = 10
        FibCompute.objects.create(index=m)

        # Compute the Fibonacci numbers 0-m the hard way.
        dispatcher.loop_while_work_exists()

        # Turn the results into an array.
        fibs = list(Fib.objects.all())
        a = [0] * (m + 1)
        for fib in fibs:
            a[fib.index] = fib.value

        assert not list(WorkExceptionLog.objects.all())

        # Now compute the same numbers the trivial way.
        expected = [0, 1] + [0] * (m - 1)
        for x in range(2, m + 1):
            expected[x] = expected[x - 1] + expected[x - 2]
        assert expected == a

    def test_do_one_work_unit(self):
        class TestWorker(Worker):
            work_unit_payload_cls = DummyPayload

            def do_work(me, wup):
                wu = wup.work_unit
                assert wu.last_attempt > start
                assert wu.state != WorkUnit.SUCCEEDED
                assert wu.succeeded_at < wu.last_attempt
                assert wu.lease_holder != ""
                work_done.append(wup)
                return True

        start = utcnow()

        dispatcher = DispatcherForTests.for_dispatcher_test(batch_size=0, worker_cls=TestWorker)
        work_done = []

        def assert_work_done(expected_work_done):
            assert dispatcher._process_one_work_batch() == 1
            assert len(work_done) == 1
            assert expected_work_done == work_done[0]
            assert not list(WorkExceptionLog.objects.all())
            del work_done[:]

        def assert_no_work_done():
            assert dispatcher._process_one_work_batch() == 0
            assert not work_done
            assert not list(WorkExceptionLog.objects.all())

        # No work to do yet.
        assert_no_work_done()

        # Check that fields are updated appropriately.
        wu1 = DummyPayload.objects.create()
        assert_work_done(wu1)
        wu1.refresh_from_db()
        assert wu1.work_unit.last_attempt > start
        assert wu1.work_unit.state == WorkUnit.SUCCEEDED
        assert wu1.work_unit.succeeded_at > start
        assert wu1.work_unit.lease_holder == ""

        # Check that work gets done in dependency order.
        # wu4 should be done before wu5, even though wu5 has an earlier last_attempt.
        wu4 = DummyPayload.objects.create()
        wu5 = DummyPayload.objects.create()
        wu5.add_requirement_by_id(wu4.work_unit_id)
        assert_work_done(wu4)
        assert_work_done(wu5)
        assert_no_work_done()

        # Check that work in all states other than READY doesn't get selected.
        for state in WorkUnit.state_to_str.keys():
            if state != WorkUnit.READY:
                work_unit = DummyPayload.objects.create().work_unit
                work_unit.state = state
                work_unit.save()
                assert_no_work_done()


class TestExecuterQueue:
    @pytest.mark.parametrize("timeout_sec", [-1, 0, 0.001, 0.04])
    def test_join_queue_invalid(self, timeout_sec: float) -> None:
        queue: Queue = Queue()
        with pytest.raises(ToolchainAssertion, match="'timeout' minimal value is 0.050"):
            join_queue(queue, timeout_sec)

    def test_join_queue_timeout_success(self) -> None:
        queue: Queue = Queue()
        queue.put("festivus")

        def thread_run():
            time.sleep(0.2)
            queue.get()
            time.sleep(0.1)
            queue.task_done()

        thread = Thread(target=thread_run, daemon=False)
        thread.start()
        assert join_queue(queue, 1) is True
        assert queue.empty() is True

    def test_join_queue_no_timeout_success(self) -> None:
        queue: Queue = Queue()
        queue.put("festivus")

        def thread_run() -> None:
            time.sleep(0.8)
            queue.get()
            time.sleep(0.3)
            queue.task_done()

        thread = Thread(target=thread_run, daemon=False)
        thread.start()
        start = time.time()
        assert join_queue(queue, None) is True
        elapsed = time.time() - start
        assert 1.4 > elapsed >= 1
        assert queue.empty() is True

    def test_join_queue_timeout_fail(self) -> None:
        queue: Queue = Queue()
        queue.put("festivus")
        start = time.time()
        assert join_queue(queue, 1) is False
        elapsed = time.time() - start
        assert 1.1 > elapsed >= 1
        assert queue.empty() is False

    def test_join_queue_timeout_empty(self) -> None:
        queue: Queue = Queue()
        start = time.time()
        assert join_queue(queue, 1) is True
        elapsed = time.time() - start
        assert elapsed <= 0.1
        assert queue.empty() is True
