# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).


class ToolchainBaseError(Exception):
    """Base class for all exceptions raised by the toolchain codebase."""


class ToolchainError(ToolchainBaseError):
    """Base class for handleable exceptions."""


class ToolchainAssertion(ToolchainBaseError):
    """Base class for non-handleable exceptions."""


class InvalidCursorError(ToolchainError):
    """Raised if we fail to parse the cursor passed back to us in queries."""


class ToolchainTransientError(ToolchainError):
    """Base class for transient errors (network issues, aws errors, etc...)."""
