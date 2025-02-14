#!/usr/bin/env ./python
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.django.service.gunicorn.toolchain_gunicorn_service import ToolchainGunicornService

if __name__ == "__main__":
    ToolchainGunicornService.from_file_name(__file__).manage()
