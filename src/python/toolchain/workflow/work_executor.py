# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
import sys
import traceback

from botocore.exceptions import NoCredentialsError
from django.db import Error as DbError
from django.db import InterfaceError, OperationalError
from prometheus_client import Histogram

from toolchain.base.contexttimer import Timer
from toolchain.base.datetime_tools import utcnow
from toolchain.django.db.transaction_broker import TransactionBroker
from toolchain.util.sentry.sentry_integration import capture_exception, execution_scope_context
from toolchain.workflow.constants import WorkExceptionCategory
from toolchain.workflow.error import FatalError, WorkException
from toolchain.workflow.models import WorkExceptionLog, WorkUnit
from toolchain.workflow.worker import Worker

WORKUNIT_LATENCY = Histogram(
    name="toolchain_workflow_workunit_latency",
    documentation="Histogram of workunit processing time labelled by work unit payload type & worker method.",
    labelnames=["payload_model", "payload_app", "method"],
    buckets=(0.1, 1.0, 2.0, 5.0, 10.0, 60.0, 90.0, 120.0, 300.0, 400.0, 600.0, 800.0, float("inf")),
)


logger = logging.getLogger(__name__)


transaction = TransactionBroker("workflow")


class TransientErrorHelper:
    _TRANSIENT_ERRORS = {
        # Some deadlocks are unavoidable, and we want to retry if they occur.
        OperationalError: ("deadlock detected", "connection reset by peer"),
        # Transient boto errors when it failed to get credentials from the local metadata service.
        NoCredentialsError: ("Unable to locate credentials",),
        InterfaceError: ("connection already closed",),
    }

    @classmethod
    def is_transient_error(cls, error) -> bool:
        error_message = str(error).lower()
        for error_type, error_messages in cls._TRANSIENT_ERRORS.items():
            if not isinstance(error, error_type):
                continue
            if any(msg in error_message for msg in error_messages):
                return True
        return False


class WorkExecutor:
    """Invokes a given worker on a given work unit.

    Invokes callbacks and updates database state based on the outcome of the work.
    """

    LONG_RUNNING_SEC = 60

    def __init__(self, work_unit: WorkUnit, worker: Worker, context: dict, log_level: int = logging.INFO) -> None:
        self._work_unit = work_unit
        self._worker = worker
        self._context = context
        self._workunit_calls_log_level = log_level

    @property
    def work_unit(self) -> WorkUnit:
        return self._work_unit

    def release(self) -> None:
        work_unit = self._work_unit
        # Just to be safe to make sure we don't try to do anything else with that work unit.
        self._work_unit = None  # type: ignore[assignment]
        logger.info(f"WorkExecutor.release {work_unit}")
        work_unit.revoke_lease()

    def execute(self) -> None:
        """Executes the work."""
        work_unit = self._work_unit
        ctype = work_unit.payload_ctype
        current_context = dict(payload_model=ctype.model, payload_app=ctype.app_label)
        current_context.update(self._context)
        extra = dict(id=work_unit.id, description=work_unit.description)
        try:
            with execution_scope_context(prefix="work_unit_", tags=current_context, extra=extra):
                self._timed(self._workunit_calls_log_level, None, self._execute)
        except Exception as ex:
            # This indicates an unlikely error in the workunit state updating code itself (!).
            # We don't know what to do with this exception, so we err on the side of strictness and
            # make it PERMANENT to alert admins that something requires attention.
            self._log_exception(work_unit, WorkException.Category.PERMANENT, ex)
            capture_exception(ex)

    def _execute(self) -> None:
        """Call do_work and handle the result (True/False/Exception).

        Handles exceptions raised in do_work() and in the on_success/on_reschedule/on_failure callbacks.
        """
        log_level = self._workunit_calls_log_level
        try:
            ret = self._timed(log_level, "do_work", self._worker.do_work, self._work_unit.payload)
        except FatalError as ex:
            capture_exception(ex)
            raise
        except Exception as ex:
            self._timed(logging.WARNING, "on_failure", self._handle_exception, ex)
            capture_exception(ex)
            return
            # We don't catch BaseException, so critical exceptions like
            # SystemExit and KeyboardInterruptError will still exit the program.

        if ret is True:
            self._timed(log_level, "on_success", self._handle_success)
        elif ret is False:
            self._timed(log_level, "on_reschedule", self._handle_reschedule)
        else:
            raise FatalError(
                f"{self._worker.__module__}.{self._worker.__class__.__name__}.do_work() must return True or False"
            )

    def _handle_success(self) -> None:
        def success_func(locked_work_unit: WorkUnit) -> None:
            self._worker.on_success(locked_work_unit.payload)
            rerun_requirers = self._worker.rerun_requirers()
            # In case the callback modified locked_work_unit's underlying db state without going
            # through the locked_work_unit instance (e.g., by adding requirements).
            # A well-behaved worker should never do that in on_success, but we want to be robust.
            locked_work_unit.refresh_from_db()
            locked_work_unit.work_succeeded(rerun_requirers)

        self._complete(success_func)

    def _handle_reschedule(self) -> None:
        def reschedule_func(locked_work_unit: WorkUnit) -> None:
            new_lease = self._worker.on_reschedule(locked_work_unit.payload)
            # In case the callback modified locked_work_unit's underlying db state without going
            # through the locked_work_unit instance (e.g., by adding requirements).
            locked_work_unit.refresh_from_db()
            locked_work_unit.leased_until = new_lease

        self._complete(reschedule_func)

    def _handle_exception(self, e: Exception) -> None:
        def failure_func(locked_work_unit: WorkUnit) -> None:
            self._worker.on_failure(locked_work_unit.payload)
            # In case the callback modified locked_work_unit's underlying db state without going
            # through the locked_work_unit instance (e.g., by adding requirements).
            # A well-behaved worker should never do that in on_failure, but we want to be robust.
            locked_work_unit.refresh_from_db()
            self._process_work_unit_exception(locked_work_unit, e)
            # We don't re-raise, so that the outer loop can continue.

        self._complete(failure_func)

    def _complete(self, completion_func) -> None:
        """Call a completion function and update the work unit state, in a single transaction.

        First refetches and locks the work unit, to verify that the worker still holds the
        lease on the work unit.

        :param completion_func: A callable that takes a single argument- the refetched work unit.
          Called in the same transaction as the one that updates the work unit state.  May return
          a timestamp, in which case the lease will continue to be held until that timestamp
          (which may be before or after the original lease expiration).  Otherwise must return None,
          and the lease expires immediately.  This only matters when rescheduling: if the work
          succeeded or failed than the lease period is no longer consulted anyway.
        """
        try:
            with transaction.atomic():
                with transaction.connection.cursor() as cursor:
                    # We improve performance significantly by not waiting for the commit to be fsynced.
                    # In the worst case, if the transaction ends up not being written due to DB server
                    # failure between the ack and the actual fsync, the DB will still be in a consistent
                    # state, so the work will get redone.
                    # See https://www.postgresql.org/docs/9.6/static/wal-async-commit.html.
                    cursor.execute("SET LOCAL synchronous_commit TO OFF;")

                # Refetch the workunit, matching on the uuid, and locking the result.
                refetch = list(self._get_refetch_queryset())
                if refetch:
                    # We still hold the lease on the work unit, so we're allowed to commit it.
                    # If not, we return silently. The dispatcher will pick up the work unit and
                    # attempt it again, since its lease has now expired.
                    locked_work_unit = refetch[0]
                    locked_work_unit.lease_holder = ""
                    locked_work_unit.leased_until = None
                    locked_work_unit.node = ""
                    # Save here, as worker callbacks may modify locked_work_unit's underlying db state without
                    # going through the locked_work_unit instance (e.g., by adding requirements).
                    locked_work_unit.save()

                    try:
                        # Inner tx is necessary, as we must catch exceptions outside an atomic block. See
                        # https://docs.djangoproject.com/en/1.11/topics/db/transactions/#django.db.transaction.atomic.
                        with transaction.atomic():
                            self._execute_completion_func(completion_func, locked_work_unit)
                            # Note that locked_work_unit is up to date with the db here, since completion_func refreshes it.
                    except Exception as ex:
                        # There was an error in the on_success/on_reschedule/on_failure callback.
                        self._process_work_unit_exception(locked_work_unit, ex)
                    locked_work_unit.save()
                    locked_work_unit.payload.save()
        except DbError as dbe:
            logger.exception(
                f"[{self._get_ident()}] Attempt to lock work unit {self._work_unit} errored.\nDue to: {dbe}"
            )
            # Continue as usual: we don't want to stop processing work because of a db error that
            # presumably has nothing to do with this specific work unit.

    def _execute_completion_func(self, completion_func, locked_work_unit):
        return completion_func(locked_work_unit)

    def _get_refetch_queryset(self):
        """Returns the QuerySet that refetches and locks a work unit if possible."""
        # Note that we only fetch the WorkUnit if it's still feasible, so we don't try to commit work
        # that was marked as infeasible while we were working on it. This allows work to be canceled in mid-flight.
        # Note that we don't filter on leased_until: If no other worker has picked up this work yet, we may as
        # well commit our result, even if we overran our lease.
        return WorkUnit.objects.filter(
            pk=self._work_unit.pk, lease_holder=self._work_unit.lease_holder, state=WorkUnit.LEASED
        ).select_for_update()

    def _process_work_unit_exception(self, locked_work_unit: WorkUnit, ex: Exception) -> None:
        category = self._get_exception_category(ex)
        self._log_exception(locked_work_unit, category, ex)
        # We check locked_work_unit.state because the work unit may already have been made infeasible
        # but then we encounter a later exception in the on_failure callback.
        if category == WorkException.Category.PERMANENT and locked_work_unit.state != WorkUnit.INFEASIBLE:
            locked_work_unit.permanent_error_occurred()
        elif category == WorkException.Category.ADVISORY:
            locked_work_unit.work_succeeded(self._worker.rerun_requirers())
        # Otherwise the error is TRANSIENT so don't modify the workunit state.
        delay = self._worker.transient_error_retry_delay(locked_work_unit.payload, ex)
        if delay:
            locked_work_unit.leased_until = utcnow() + delay

    def _log_exception(self, work_unit: WorkUnit, category: WorkExceptionCategory, ex: Exception) -> None:
        """Log an exception into the database."""
        stacktrace_str = self._generate_exception_stacktrace()
        WorkExceptionLog.create(category=category, work_unit=work_unit, error=ex, stacktrace=stacktrace_str)

    def _get_exception_category(self, error: Exception) -> WorkExceptionCategory:
        category = self._worker.classify_error(error)
        if category:
            return category
        if isinstance(error, WorkException):
            return error.category
        # Keeping TransientErrorHelper.is_transient_error for now, until we migrate some logic into workers.
        return (
            WorkException.Category.TRANSIENT
            if TransientErrorHelper.is_transient_error(error)
            else WorkException.Category.PERMANENT
        )

    @staticmethod
    def _generate_exception_stacktrace() -> str:
        tb = sys.exc_info()[2]
        tb_lines = traceback.format_tb(tb)
        if any("\t" in line for line in tb_lines):
            stacktrace_str = "No stacktrace captured due to embedded tabs"
        else:
            stacktrace_str = "\t".join(traceback.format_tb(tb))
        return stacktrace_str

    def _timed(self, log_level: int, method_name: str | None, func, *args, **kwargs):
        with Timer() as timer:
            try:
                ret = func(*args, **kwargs)
            finally:
                if method_name:
                    ct = self._work_unit.payload_ctype
                    WORKUNIT_LATENCY.labels(
                        payload_model=ct.model, payload_app=ct.app_label, method=method_name
                    ).observe(timer.elapsed)
                long_running = "long_running" if timer.elapsed >= self.LONG_RUNNING_SEC else ""
                logger.log(
                    logging.INFO if long_running else log_level,
                    f"[{self._get_ident()}] Executed `{func.__name__}()` in {timer.elapsed:.3f}s "
                    f"for workunit #{self._work_unit.pk} ({self._work_unit.payload}) {long_running}",
                )
        return ret

    def _get_ident(self):
        return self._work_unit.get_ident()

    def __str__(self) -> str:
        return str(self._work_unit)
