# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from enum import Enum, unique


@unique
class WorkExceptionCategory(Enum):
    # Indicates an event that is worth noting, but does not fail the work.
    ADVISORY = "ADVISORY"

    # Indicates an event that may be transient, so the work can be retried later.
    TRANSIENT = "TRANSIENT"

    # Indicates a permanent error, so the work should not be retried later (at least until
    # the cause of the error has been dealt with somehow).
    PERMANENT = "PERMANENT"

    @classmethod
    def get_choices(cls) -> tuple[tuple[str, str], ...]:
        return tuple((mem.value, mem.value.lower()) for mem in cls)
