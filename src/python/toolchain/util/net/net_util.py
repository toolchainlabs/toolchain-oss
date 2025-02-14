# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import os
import socket
import subprocess

from toolchain.base.memo import memoized
from toolchain.base.toolchain_error import ToolchainAssertion


@memoized
def get_remote_username() -> str:
    username_override = os.environ.get("TOOLCHAIN_USER")
    if username_override:
        return username_override
    cmd = ["ssh", "-G", "bastion.toolchain.private"]
    user_line = subprocess.check_output(cmd).decode().splitlines(keepends=False)[0]
    user_line_parts = user_line.split()
    if user_line_parts[0] != "user":
        raise ToolchainAssertion(f"Expected user name in first output line of: {cmd}")
    return user_line_parts[1]


def hostname_resolves(hostname: str) -> bool:
    try:
        socket.gethostbyname(hostname)
        return True
    except OSError:
        return False


def can_connect(host: str, port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    ret = sock.connect_ex((host, port))
    return ret == 0
