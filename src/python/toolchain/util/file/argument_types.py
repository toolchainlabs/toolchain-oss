# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import contextlib
from argparse import ArgumentTypeError

from toolchain.util.file.base import Directory
from toolchain.util.file.create import create
from toolchain.util.file.errors import InvalidUrlError
from toolchain.util.file.local import LocalDirectory


def directory_url(val):
    """An argparse argument type for a directory URL."""
    with contextlib.suppress(InvalidUrlError):
        if isinstance(create(val), Directory):
            return val
    raise ArgumentTypeError(f"Not a directory URL: {val}")


def local_directory_url(val):
    """An argparse argument type for a local directory URL."""
    with contextlib.suppress(InvalidUrlError):
        if isinstance(create(val), LocalDirectory):
            return val
    raise ArgumentTypeError(f"Not a local directory URL: {val}")
