# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import abc
import datetime

from toolchain.workflow.constants import WorkExceptionCategory
from toolchain.workflow.models import WorkUnitPayload


class Worker(abc.ABC):
    """A base class for classes that do actual work.

    A new instance will be created for each attempt on each work unit, so the worker is allowed to store state on itself
    in do_work(), to be referenced in on_success()/on_failure().

    Each subclass of Worker must handle the work described by one subclass of WorkUnit.
    """

    # Subclasses can override to specify a default lease time for their work.
    DEFAULT_LEASE_SECS: float = 300

    @property
    @abc.abstractmethod
    def work_unit_payload_cls(self) -> type[WorkUnitPayload]:
        """Subclasses must override to specify the type of payload that they're capable of handling."""

    def __init__(self, *args, **kwargs):
        """Subclasses must pass any args/kwargs they don't themselves consume to this ctor.

        This future-proofs those subclasses against any changes to this ctor's arguments, even though the current
        implementation is a no-op.
        """
        super().__init__()

    def lease_secs(self, work_unit) -> float:
        """Returns the number of seconds this worker will hold a lease on its work unit for.

        Subclasses can override DEFAULT_LEASE_SECS above to set a single lease length for all workers of that type, or
        they can override this method to set a custom lease length for each worker, possibly based on the work_unit.
        """
        return self.DEFAULT_LEASE_SECS

    def do_work(self, work_unit_payload: WorkUnitPayload) -> bool:
        """Implement this to perform the work described by work_unit_payload.

        Implementations should:

        - Raise an exception to indicate that the work failed.
        - Return True to indicate that the work completed successfully.
        - Return False to indicate that the work should be rescheduled for another attempt.
          This is typically used when the worker needs to create more requirements for
          work_unit and wishes to retry only after those requirements are satisfied.

        This method must not modify work_unit_payload or store a reference to it.
        It may store state on itself and use that to modify the work_unit_payload in the on_*()
        handlers, e.g., to provide extra information about the handled condition.

        :param work_unit_payload: Perform the work described by this WorkUnitPayload instance.
        """
        raise NotImplementedError()

    def rerun_requirers(self) -> bool:
        """Should requirers of work re-run in do_work() also be re-run.

        This will be called after do_work().  The requirers of the work re-run by do_work() will themselves be re-run
        iff this method returns True. An implementation of do_work() can store state on this object and use it to decide
        if requirers need to be re-run. This allows re-runs to short-circuit, e.g., if a fetched web resource hasn't
        changed.
        """
        return True

    def on_success(self, work_unit_payload: WorkUnitPayload) -> None:
        """Override this to perform any database updates resulting from success of the work.

        These updates will happen in the same transaction as the one that updates the work unit state.

        This method is allowed to modify work_unit_payload, and need not call save() on it,
        as the dispatcher will always do so.

        Note that:
          - The work_unit-payload argument represents the same WorkUnitPayload as the one passed to do_work,
            but it may not be the same object.
          - This method might not be called if the worker loses its lease before do_work() completes.

        :param work_unit_payload: The payload of the successful work unit.
        """
        return None

    def on_reschedule(self, work_unit_payload: WorkUnitPayload) -> datetime.datetime | None:
        """Override this to perform any database updates resulting from rescheduling the work.

        These updates will happen in the same transaction as the one that updates the work unit state.

        There are two ways to reschedule:

        - By requirement: Use this method to add new requirements to the work.

        - By time: Return a timestamp from this method, and the work unit will not be re-attempted
          until after that timestamp.

        You may use both together, but if you use neither the work unit will be eligible to be
        re-attempted immediately, with no other state having changed, which makes rescheduling it
        pointless.

        This method is allowed to modify work_unit_payload, and need not call save() on it,
        as the dispatcher will always do so.

        Note that:
          - The work_unit-payload argument represents the same WorkUnitPayload as the one passed to do_work,
            but it may not be the same object.
          - This method might not be called if the worker loses its lease before do_work() completes.

        :param work_unit_payload: The payload of the rescheduled work unit.
        :return: A timestamp to reschedule after.
        """
        return None

    def on_failure(self, work_unit_payload: WorkUnitPayload) -> None:
        """Override this to perform any database updates resulting from failure of the work.

        These updates will happen in the same transaction as the one that updates the work unit state.

        This method is allowed to modify work_unit_payload, and need not call save() on it,
        as the dispatcher will always do so.

        Note that:
          - The work_unit-payload argument represents the same WorkUnitPayload as the one passed to do_work,
            but it may not be the same object.
          - This method might not be called if the worker loses its lease before do_work() completes.

        :param work_unit_payload: The payload of the failed work unit.
        """
        return None

    def classify_error(self, exception: Exception) -> WorkExceptionCategory | None:
        """Override this to classify errors raised from do_work.

        This method allows subclasses to check any exception attributes (including type) in order to determine the
        category of the error and thus determining if the work unit should be retried or not.
        """
        return None

    def transient_error_retry_delay(
        self, work_unit_payload: WorkUnitPayload, exception: Exception
    ) -> datetime.timedelta | None:
        """Override this to specicy a delay before retrying the work unit in case of a transient error.

        This method allows subclasses to check specify a delay before the work unit will be retried in case of a
        trainsent error. The default behavior is to retry immediately (when the next worker is able to run work units)
        """
        return None
