# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.base.toolchain_error import ToolchainError


class StaleResponse(ToolchainError):
    pass


class NoProjectData(ToolchainError):
    pass


class TransientError(ToolchainError):
    """Raised when transient (network/http) errors occur."""
