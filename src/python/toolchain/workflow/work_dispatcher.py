# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
import random
import time
from collections.abc import Sequence
from datetime import timedelta
from functools import reduce
from queue import Queue
from typing import cast

from django.db.models import Q, QuerySet
from prometheus_client import Counter, Gauge

from toolchain.base.datetime_tools import utcnow
from toolchain.base.node_id import get_node_id
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.django.db.transaction_broker import TransactionBroker
from toolchain.workflow.config import WorkflowWorkerConfig
from toolchain.workflow.error import FatalError
from toolchain.workflow.models import WorkUnit, WorkUnitPayload
from toolchain.workflow.system_signals import SignalWrapper
from toolchain.workflow.work_executor import WorkExecutor
from toolchain.workflow.worker import Worker
from toolchain.workflow.worker_thread import WorkerThread

logger = logging.getLogger(__name__)

random.seed()
transaction = TransactionBroker("workflow")
WorkerClasses = tuple[type[Worker], ...]
WorkerPayloads = Sequence[type[WorkUnitPayload]]

MIN_TIMEOUT_SEC = 0.05  # 50msec

DISPATCHER_WORK_UNITS_COUNT = Counter(
    name="toolchain_workflow_dispatcher_processed_work_units",
    documentation="Number of workunits processed via work dispatcher",
    labelnames=["dispatcher_cls"],
)


WORK_UNIT_LAST_ATTEMPT = Gauge(
    name="toolchain_workflow_workunit_last_attempt",
    documentation="Last attempt time for work units by payload model type",
    labelnames=["payload_model", "payload_app"],
)


def join_queue(queue: Queue, timeout: float | None = None) -> bool:
    """Waits for all the items in the queue to be consumed and marked as done, up to a timeout (if specified)

    Returns True if the queue was successfully joined. Returns False if the timout expired. # Based
    https://bugs.python.org/msg157458 via https://bugs.python.org/issue9634
    """
    if timeout is None:
        queue.join()
        return True
    elif timeout < MIN_TIMEOUT_SEC:
        raise ToolchainAssertion(f"'timeout' minimal value is {MIN_TIMEOUT_SEC:.3f}")
    queue.all_tasks_done.acquire()
    endtime = time.time() + timeout
    try:
        while queue.unfinished_tasks:
            remaining = endtime - time.time()
            if remaining <= 0.0:
                return False
            queue.all_tasks_done.wait(remaining)
        return True
    finally:
        queue.all_tasks_done.release()


class WorkDispatcher:
    """Dispatches work to workers."""

    singleton = None

    # If there's no work to do, sleep this long before looking for more.
    # Subclasses can override with a class or instance field.
    sleep_secs = 2.0
    # We want to log to info roughly every 500 cycles even if we didn't fetch any work
    empty_fetch_log_rate = 500

    @classmethod
    def for_tests(cls):
        worker_classes = cls.worker_classes
        WorkDispatcher.singleton = None
        payload_types = cast(WorkerPayloads, [worker_cls.work_unit_payload_cls for worker_cls in worker_classes])
        return cls(
            num_executor_threads=0,
            batch_size=1,
            work_payload_types=payload_types,
            node="test",
            worker_classes=worker_classes,
            worker_calls_log_level=logging.INFO,
        )

    @classmethod
    def for_worker_classes(cls, *, config: WorkflowWorkerConfig, worker_classes: WorkerClasses):
        payload_types = cast(WorkerPayloads, [worker_cls.work_unit_payload_cls for worker_cls in worker_classes])
        return cls(
            num_executor_threads=config.num_executor_threads,
            batch_size=config.batch_size,
            node=get_node_id(),
            work_payload_types=payload_types,
            worker_classes=worker_classes,
            worker_calls_log_level=config.worker_calls_log_level,
        )

    def __init__(
        self,
        *,
        num_executor_threads: int,
        batch_size: int,
        work_payload_types: WorkerPayloads,
        node: str,
        worker_calls_log_level: int,
        context: dict[str, str] | None = None,
        worker_classes: WorkerClasses | None = None,
    ):
        """
        :param int num_executor_threads: Offload the actual work execution to this number of threads.
        :param int batch_size: Fetch this many work units per batch.  Defaults to 2x the concurrency level
                               (2x num_executor_threads or 2 if no threads).
                               Larger numbers will mean fewer complex work-fetching db queries, and so
                               may decrease database load, at the expense of "tying up" more work units.
        :param work_payload_types: A list of work payload types to fetch.  If unspecified, any type of work
                                   will be eligible to be fetched.
        :param node: An optional identifier for the node this dispatcher is running on.
                     Useful for status reporting, but not required for correctness.
                     The meaning of "node" is unspecified, but useful examples include Kubernetes pod name,
                     host:port, host.pid etc. (Do not confuse with a Kubernetes node, which is an entire host).
        :param worker_calls_log_level: the log level used when logging calls to worker methods (do_work, on_success, etc...)
        :param context: An optional set of tags that will get attached to errors (exception) reported to sentry.
        :param worker_classes: An optional list of worker classes to register
        """
        # Note that we want one singleton for all subclasses, so we reference the class explicitly.
        if WorkDispatcher.singleton is not None:
            raise ToolchainAssertion("Cannot create more than one WorkDispatcher instance per process.")
        WorkDispatcher.singleton = self
        self._worker_calls_log_level = worker_calls_log_level
        self._num_executor_threads = num_executor_threads or 1
        if self._num_executor_threads < 1:
            raise ToolchainAssertion("Invalid number of execution threads.")
        self._batch_size = batch_size or 2 * self._num_executor_threads or 2
        self._type_to_ctype_id = {ct.model_class(): ct.pk for ct in transaction.content_type_mgr.all()}
        if work_payload_types:
            payload_ctype_ids = (self._type_to_ctype_id[wt] for wt in work_payload_types)
            self._type_filter = reduce(
                lambda x, y: x | y, (Q(payload_ctype_id=ctype_id) for ctype_id in payload_ctype_ids)
            )
        else:
            self._type_filter = None
        payload_type_names = ", ".join(pt.__name__ for pt in work_payload_types) if work_payload_types else "N/A"
        logger.info(
            f"Creating {type(self).__name__} work dispatcher node={node} batch_size={self._batch_size} threads={self._num_executor_threads} work_types=[{payload_type_names}]"
        )
        self._payload_ctype_id_to_worker_factory: dict[type, type] = {}
        for worker_cls in worker_classes or []:
            self.register_worker_cls(worker_cls)
        self._node = node
        self._context = dict(context) if context else {}  # Defensive copy.
        # The main thread queries the db for work and enqueues it for the worker threads to dequeue.
        # The queue maxsize is selected to allow one work unit to wait in the pipeline per thread.
        # This means that threads (or at least the ones whose work is slower than the db query that
        # fetches the work) aren't idle waiting on the db query.
        # We don't want an arbitrarily large queue size though, as we hold the lease for everything
        # in the queue, so no other process can do that queued work.
        self._executor_queue: Queue = Queue(maxsize=self._batch_size)
        self._signals = SignalWrapper()
        self._stop_requested = False

    @property
    def _should_stop(self) -> bool:
        return self._stop_requested or self._signals.should_quit

    def init_threads(self) -> None:
        self._threads = [WorkerThread(self._executor_queue) for _ in range(self._num_executor_threads)]
        for worker_thread in self._threads:
            worker_thread.start()

    def run_workflow_forever(self) -> None:
        self.init_threads()
        try:
            self.work_loop()
        finally:
            self._stop_threads()
        logger.info("Exit work dispatcher thread.")

    def _check_worker_threads_liveness(self) -> bool:
        """Check if any of the worker threads died.

        Returns True if all threads are alive, False if any of the threads has died.
        TODO: Implement a keep-alive mechanism and make sure workers periodically update a timestamp (to detect hanging threads)
        """
        dead_workers = sum(not worker_thread.is_alive() for worker_thread in self._threads)
        if dead_workers > 0:
            logger.warning(f"dead_workers_detected {dead_workers=}.")
            return True
        return False

    def register_worker_cls(self, worker_cls: type[Worker]) -> None:
        """Register a worker class that handles work units of a declared type.

        :param worker_cls: A subclass of `toolchain.workflow.worker.Worker` that defines
                           a class-level work_unit_payload_cls property, which must be a subclass of
                           `toolchain.workflow.models.WorkUnitPayload`.
                           This Worker subclass's `__init__` method must take a single argument
                           (the work unit instance).
        """
        if worker_cls.work_unit_payload_cls is None:
            raise FatalError(f"Worker subclass {worker_cls} does not specify a work_unit_payload_cls")
        self.register_worker_factory(worker_cls.work_unit_payload_cls, worker_cls)

    def register_worker_factory(self, work_unit_payload_cls, worker_factory) -> None:
        """Register a factory for creating worker instances to handle work units of the given type.

        :param work_unit_payload_cls: A subclass of `toolchain.workflow.models.WorkUnitPayload`.
        :param worker_factory: A callable that takes no arguments and returns an instance of
                               an appropriate subclass of `toolchain.workflow.worker.Worker`.
        """
        ctype_id = self._type_to_ctype_id[work_unit_payload_cls]
        self._payload_ctype_id_to_worker_factory[ctype_id] = worker_factory

    def get_queued_work_units(self) -> list[WorkUnit]:
        """Returns the work units currently in the queue, waiting to be claimed by a worker thread."""
        # Note: relies on internals of Queue.
        with self._executor_queue.mutex:
            return [x.work_unit for x in self._executor_queue.queue]

    def stop(self) -> None:
        self._stop_requested = True

    def _stop_threads(self) -> None:
        logger.info("Stopping worker threads")
        for thread in self._threads:
            thread.stop_worker()
        logger.info("Join worker threads")
        for thread in self._threads:
            thread.join(1)

    def work_loop(self) -> None:
        """Main work loop."""
        while not self._should_stop:
            self.loop_while_work_exists()
            has_dead_workers = self._check_worker_threads_liveness()
            if has_dead_workers:
                return
            logger.debug(f"No work to do. Sleeping for {self.sleep_secs} seconds.")
            time.sleep(self.sleep_secs)

    def loop_while_work_exists(self) -> None:
        """Do all work that can currently be done."""
        while not self._should_stop:
            if not self._process_one_work_batch():
                # We get here when there's no more work in the db to enqueue.
                # Wait until all the workers are idle.
                join_queue(self._executor_queue)
                if not self._process_one_work_batch():
                    # All workers are idle and there's still no work in the db, so nothing
                    # in this process can create new work.  Therefore we return and let our
                    # caller decide what to do.  E.g., in a test this means we're done, and in
                    # production we can sleep for a short time before checking if any other
                    # processes have created work for us to do.
                    break

    def _process_one_work_batch(self) -> int:
        """Fetch and process a work batch.

        If we're in single-thread mode, executes the work synchronously in the calling thread.
        Otherwise enqueues the work, to be executed by worker threads.

        :return int: Number of work units we are processing
        """
        if self._should_stop:
            return 0
        executors = self._fetch_one_work_batch()
        # Enqueue a batch of work for the worker threads to execute.
        for executor in executors:
            # If the queue is full, put() will block until a slot opens up.
            self._executor_queue.put(executor)
        DISPATCHER_WORK_UNITS_COUNT.labels(dispatcher_cls=type(self).__name__).inc(amount=len(executors))
        return len(executors)

    def _fetch_one_work_batch(self) -> list[WorkExecutor]:
        """Fetches a batch of work from the database.

        :return: A list of WorkExecutor instances ready to be executed.  An empty list indicates
                 that there's no work currently eligible to be performed.
        """
        executors = []
        now = utcnow()
        logger.debug("Fetching work batch...")
        with transaction.atomic():
            qs = self._get_queryset()
            work_units = list(qs)  # list() evaluates the QuerySet, causing the database roundtrip.
            for work_unit in work_units:
                worker = self._get_worker(work_unit)
                # Note that if lease_holder is currently set to the uuid of some other worker, then that
                # worker's lease has expired, so overwrite, preventing that worker from committing.
                work_unit.take_lease(
                    until=now + timedelta(seconds=worker.lease_secs(work_unit)), last_attempt=now, node=self._node
                )
                ct = work_unit.payload_ctype
                WORK_UNIT_LAST_ATTEMPT.labels(payload_model=ct.model, payload_app=ct.app_label).set(
                    int(now.timestamp())
                )
                executors.append(WorkExecutor(work_unit, worker, self._context, log_level=self._worker_calls_log_level))
        # We want to log to info roughly every X cycles even if we didn't fetch any work
        level = logging.INFO
        if not executors and random.randint(0, self.empty_fetch_log_rate) != 0:  # nosec: B311
            level = logging.DEBUG
        logger.log(level=level, msg=f"Fetched {len(executors)} work units in {(utcnow()-now).total_seconds():.3f}s.")
        return executors

    def _get_worker(self, work_unit: WorkUnit) -> Worker:
        worker_cls = self._payload_ctype_id_to_worker_factory.get(work_unit.payload_ctype_id)
        if worker_cls is None:
            raise FatalError(
                f"No Worker subclass registered for work unit {work_unit!r} of type {work_unit.payload_ctype.name}"
            )
        return worker_cls()

    def _get_queryset(self):
        """Returns a QuerySet suitable for fetching available work units.

        The queryset will return up to num_executor_threads work units (or a single work unit if we're in single-thread
        mode).

        A work unit is available if it hasn't succeeded since our lower bound, it's not blocked on any requirements, and
        its lease isn't held.
        """
        qs = WorkUnit.objects.filter(state=WorkUnit.READY)
        if self._type_filter is not None:
            qs = qs.filter(self._type_filter)
        qs = self.apply_work_unit_filter(qs)
        # Note that we don't order the query, as that would make it significantly less efficient.
        qs = qs[: self._batch_size].select_for_update(skip_locked=True)
        return qs

    def apply_work_unit_filter(self, queryset: QuerySet) -> QuerySet:
        """Allows subclasses to limit the work units that will run based on custom criteria."""
        return queryset
