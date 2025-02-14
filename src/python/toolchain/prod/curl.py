#!/usr/bin/env ./python
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import os
import subprocess
import sys

from toolchain.pants.auth.client import AuthClient
from toolchain.pants.auth.subsystems import DEFAULT_AUTH_FILE


# This script does not use ToolchainBinary because it is intended to be a thin wrapper around curl.
# It just obtains an access key and does minimal modification of the argument list before invoking `curl`.
def main(original_args: list[str]) -> int:
    base_url = "https://app.toolchain.com/api/v1"
    auth_options = AuthClient.create(
        context="curl",
        pants_bin_name="dummy",
        base_url=base_url,
        auth_file=DEFAULT_AUTH_FILE,
        env_var=None,
        ci_env_vars=tuple(),
    )
    auth_token = auth_options.acquire_access_token(dict(os.environ))
    for i, arg in enumerate(original_args):
        if arg.startswith("/"):
            original_args[i] = base_url + arg

    args = ["curl", "--header", f"Authorization: Bearer {auth_token.access_token}"] + original_args
    return subprocess.call(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
