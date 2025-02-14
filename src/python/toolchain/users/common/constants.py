# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from enum import Enum, unique


@unique
class AuthProvider(Enum):
    GITHUB = "github"
    BITBUCKET = "bitbucket"
