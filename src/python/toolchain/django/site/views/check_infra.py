# Copyright 2016 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.views import View

from toolchain.base.toolchain_error import ToolchainError


class DummyError(ToolchainError):
    pass


class CheckSentryz(View):
    view_type = "checks"

    def get(self, _):
        raise DummyError("Testing sentry integration.")
