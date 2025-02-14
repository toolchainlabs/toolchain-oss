# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime

from toolchain.base.toolchain_error import ToolchainAssertion, ToolchainError
from toolchain.workflow.constants import WorkExceptionCategory


class WorkException(ToolchainError):
    """An exception indicating failure to process a unit of work."""

    Category = WorkExceptionCategory

    # Subclasses must set.
    category: WorkExceptionCategory


class AdvisoryWorkException(WorkException):
    category = WorkException.Category.ADVISORY


class TransientWorkException(WorkException):
    category = WorkException.Category.TRANSIENT

    def __init__(self, msg: str, retry_delay: datetime.timedelta | None = None) -> None:
        super().__init__(msg)
        self.retry_delay = retry_delay


class PermanentWorkException(WorkException):
    category = WorkException.Category.PERMANENT


class FatalError(ToolchainAssertion):
    """A logic error indicating that the work loop should terminate."""
