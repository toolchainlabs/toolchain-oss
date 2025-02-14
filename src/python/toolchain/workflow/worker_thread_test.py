# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import time
from queue import Queue

import pytest

from toolchain.workflow.worker_thread import WorkerThread


class FakeExecutor:
    def __init__(self) -> None:
        self.called = ""

    def execute(self) -> None:
        if self.called:
            raise AssertionError(f"Already called: {self.called}")
        self.called = "execute"

    def release(self) -> None:
        if self.called:
            raise AssertionError(f"Already called: {self.called}")
        self.called = "release"


class TestWorkerThread:
    def test_do_work_empty_queue(self) -> None:
        queue: Queue = Queue()
        wt = WorkerThread(queue)
        assert wt.get_time_since_ping() < 0.01
        start = time.time()
        assert wt._do_work() is False
        # do_work should block for 0.3sec if queue is empty.
        # However tests can have timing issues, so allowing up to one second of skew here.
        assert time.time() - start == pytest.approx(0.3, rel=1)
        assert wt.get_time_since_ping() == pytest.approx(0.3, rel=1)

    def test_do_work(self) -> None:
        work = FakeExecutor()
        queue: Queue = Queue()
        queue.put(work)
        wt = WorkerThread(queue)
        start = time.time()
        assert wt._do_work() is True
        assert int((time.time() - start) * 100) == 0
        assert int(wt.get_time_since_ping() * 000) == 0
        assert work.called == "execute"
        assert queue.empty() is True

    def test_release(self) -> None:
        work1 = FakeExecutor()
        work2 = FakeExecutor()
        queue: Queue = Queue()
        queue.put(work1)
        queue.put(work2)
        wt = WorkerThread(queue)
        wt.stop_worker()
        assert wt._do_work() is True
        assert work1.called == "release"
        assert work2.called == ""
        assert wt._do_work() is True
        assert work2.called == "release"
        assert queue.empty() is True
        assert wt._do_work() is False
