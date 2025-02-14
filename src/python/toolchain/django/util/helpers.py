# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from enum import Enum


def get_choices(enum: type[Enum]) -> tuple[tuple[str, str], ...]:
    return tuple((member.value, member.name) for member in enum)
