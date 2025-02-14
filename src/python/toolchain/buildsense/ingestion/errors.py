# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.base.toolchain_error import ToolchainError


class BadDataError(ToolchainError):
    """Raised if the build/run data provided is malformed."""
