#!/usr/bin/env python3
# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).
# ^^^^^^^^^^^^^^^^^^^^
# NOTE: This looks for a system Python and not our bootstrapped "./python" because it is used
# by the very setup scripts that bootstrap the environment in which "./python" runs.
#
# ----
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Compute the MD5 checksum of a file. "Why not use an existing system utility?" Very good question! Because
# macOS has `md5` and Linux has `md5sum` and they different output formats. Instead of switching on OS platform
# and normalizing the outputs, the more reliable way is to just directly implement the checksum functionality
# in this script.

import hashlib
import sys


def hash_file(filename):
    h = hashlib.md5()
    with open(filename, 'rb') as f:
        data = f.read()
        h.update(data)
    return h.hexdigest()


def main(args):
    for arg in args:
        digest = hash_file(arg)
        print(f"{digest}  {arg}")


if __name__ == '__main__':
    main(sys.argv[1:])
