# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.pants.internal.setup_py import toolchain_setup_rules


def rules():
    return (*toolchain_setup_rules(),)
