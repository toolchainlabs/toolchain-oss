# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.pants.auth.server import TestPage

# Prevent pytest from trying to collect TestPage enum as tests:
TestPage.__test__ = False  # type: ignore[attr-defined]
