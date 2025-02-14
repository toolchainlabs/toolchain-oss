# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import inspect


def get_calling_context() -> tuple[type | None, int | None]:
    """Returns the workflow context in which this method was called.

    Returns the (Worker subclass, WorkUnit pk) for the WorkExecutor instance that (indirectly) called this method.

    Allows us to populate a new WorkUnit's "creator" field without plumbing the creating context through, when that new
    WorkUnit is created inside an on_success/reschedule/failure callback for another WorkUnit (the one returned by this
    method).
    """
    for frame_record in inspect.stack():
        frame = frame_record[0]
        instance = inspect.getargvalues(frame).locals.get("self")
        # Note that checks for the class and method are via strings, not references to the actual class/method,
        # because we don't want to depend on WorkExecutor here. Doing so would cause a circular dep
        # (work_executor.py -> models.py -> work_executor.py).
        if type(instance).__name__ == "WorkExecutor" and inspect.getframeinfo(frame)[2] == "_execute_completion_func":
            return type(instance._worker), instance._work_unit.pk  # type: ignore[union-attr]
    return None, None
