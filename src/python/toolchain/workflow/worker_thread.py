# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
import time
from queue import Empty, Queue
from threading import Thread

from toolchain.workflow.work_executor import WorkExecutor

logger = logging.getLogger(__name__)


class WorkerThread(Thread):
    """A thread that consumes work from a queue and performs it."""

    def __init__(self, executor_queue: Queue) -> None:
        super().__init__()
        # The name defaults to 'Thread-N' with N a small integer. We capture this integer, as it's
        # more useful than the thread ident (which can be a large integer).
        self.thread_number = self.name[self.name.find("-") + 1 :]
        # We add a prefix to more easily distinguish these threads in debug data.
        self.name = f"Worker{self.name}"
        self.daemon = True  # So the process exits when the main thread does.
        self._executor_queue = executor_queue
        self._should_exit = False
        self._ping_keep_alive()

    def _ping_keep_alive(self) -> None:
        self._keep_alive = time.time()

    def get_time_since_ping(self) -> float:
        return time.time() - self._keep_alive

    def stop_worker(self) -> None:
        self._should_exit = True
        logger.info(f"Stopping worker thread: {self.name}")

    def _get_executor(self) -> WorkExecutor | None:
        try:
            return self._executor_queue.get(block=True, timeout=0.3)
        except Empty:
            return None

    def _do_work(self) -> bool:
        self._ping_keep_alive()
        executor = self._get_executor()
        # if there are WorkExecutor in the queue, we want to release as many of them before exiting.
        # so only return if there is no executers in the queue.
        if not executor:
            return False
        self._ping_keep_alive()
        try:
            if self._should_exit:
                executor.release()
            else:
                executor.execute()
        finally:
            self._executor_queue.task_done()
        return True

    def run(self) -> None:
        # Note that when the process exits this thread will exit abruptly, with no
        # chance to clean up after itself. Since work is supposed to be committed
        # transactionally, this is fine. In any case, we need to be robust to sudden
        # interruption (nothing can guarantee that it won't happen), so we might as
        # well make that the normal shutdown mode.
        while True:
            did_work = self._do_work()
            if not did_work and self._should_exit:
                logger.info("Exit worker thread")
                return
