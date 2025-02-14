# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import re

from toolchain.base.toolchain_error import ToolchainError

_req_re = re.compile(r"^(?P<project_name>[^\s=]+)==(?P<version>[^\s]+) --hash=sha256:(?P<sha256>[0-9a-f]{64})$")


def parse_lockfile_line(line):
    m = _req_re.match(line)
    if m is None:
        raise ToolchainError(f"Not a valid lockfile line: {line}")
    return m.group("project_name"), m.group("version"), m.group("sha256")


def parse_lockfile(lockfile):
    with open(lockfile, encoding="utf-8") as fp:
        for line in fp.readlines():
            yield parse_lockfile_line(line)
