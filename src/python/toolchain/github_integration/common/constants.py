# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from enum import Enum, unique


@unique
class RepoState(Enum):
    # We never delete GithubRepo objects. just mark then inactive
    ACTIVE = "active"
    INACTIVE = "inactive"
