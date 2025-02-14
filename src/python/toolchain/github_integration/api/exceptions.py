# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.base.toolchain_error import ToolchainError


class CIResolveError(ToolchainError):
    def __init__(self, ci_type: str, error: str) -> None:
        super().__init__(f"ci={ci_type} {error}")
