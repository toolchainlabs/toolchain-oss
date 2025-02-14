#!/usr/bin/env python3
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import argparse
import json
import logging
import os
import subprocess
from argparse import ArgumentParser, Namespace
from pathlib import Path
from urllib.parse import urlparse

import httpx

from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.base.toolchain_error import ToolchainAssertion

logger = logging.getLogger(__name__)


class WithCasToken(ToolchainBinary):
    """Invokes an executable with the Toolchain auth token and instance name.

    Useful for invoking `casload`, `smoketest`, and other REAPI tools. The following environment variables will be set
    for the invoked executable: `TC_AUTH_TOKEN`, JWT for authorization; `TC_INSTANCE`, REAPI instance name that is
    authorized by the JWT; `TC_ENDPOINT`, cache endpoint to use in grpcs://-format.
    """

    # Potential default locations for Toolchain source.
    SOURCES = ("~/toolchain", "~/TC/toolchain", "~/projects/toolchain")

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)

        if cmd_args.source:
            source = Path(cmd_args.source).expanduser()
        else:
            found_source = False
            for candidate_source in self.SOURCES:
                source = Path(candidate_source).expanduser()
                if source.exists():
                    found_source = True
                    break
            if not found_source:
                raise ToolchainAssertion(
                    f"Unable to find Toolchain source location in any of the default locations: {','.join(self.SOURCES)}"
                )
        # see pants.localdev.toml `[auth].auth_file` for the location of the dev file.
        auth_token_filename = "auth-dev.json" if cmd_args.dev else "auth_token.json"
        self._auth_token_path = source / ".pants.d" / "toolchain_auth" / auth_token_filename
        if not self._auth_token_path.exists():
            raise ToolchainAssertion(f"Refresh token file {self._auth_token_path} does not exist.")

        if cmd_args.dev:
            self._auth_host_base_url = "http://127.0.0.1:9500"
        elif cmd_args.staging:
            self._auth_host_base_url = "https://staging.app.toolchain.com"
        else:
            self._auth_host_base_url = "https://app.toolchain.com"
        self._args = cmd_args.args
        self._is_dev = cmd_args.dev
        logger.info(f"token path: {self._auth_token_path} auth/token host: {self._auth_host_base_url}")

    def run(self) -> int:
        refresh_token_str = json.loads(self._auth_token_path.read_text())["access_token"]
        resp = httpx.post(
            url=f"{self._auth_host_base_url}/api/v1/token/refresh/",
            headers={
                "Authorization": f"Bearer {refresh_token_str}",
                "User-Agent": "with-cas-token-tool",
            },
        )
        resp.raise_for_status()
        logger.debug(f"{resp.text=}\n")
        resp_json = resp.json()
        token_json = resp_json["token"]
        instance = token_json["customer_id"]
        cache_netloc = urlparse(resp_json["remote_cache"]["address"]).netloc  # Strip the grpcs:// from the response
        env = os.environ.copy()
        self._args.extend(("--remote", cache_netloc, "--instance-name", instance, "--auth-token-env", "TC_AUTH_TOKEN"))
        self._args.append("--allow-insecure-auth" if self._is_dev else "--secure")
        env.update(TC_AUTH_TOKEN=token_json["access_token"])
        logger.info(f"Running: {' '.join(self._args)}")
        try:
            output = subprocess.check_output(self._args, env=env).decode()
        except subprocess.CalledProcessError as error:
            error_output = ((error.stderr or b"") + (error.stdout or b"")).decode()  # type: ignore
            logger.error(f"Failed: {error.returncode=} output={error_output or 'N/A'}")
            return -1
        logger.info(output)
        return 0

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        super().add_arguments(parser)
        parser.add_argument("--dev", "-d", action="store_true", help="use dev token")
        parser.add_argument("--source", "-S", action="store", default=None, help="path to the toolchain source code")
        parser.add_argument(
            "--staging", "-s", action="store_true", default=False, help="use staging buildsense endpoint"
        )
        parser.add_argument("args", nargs=argparse.REMAINDER)


if __name__ == "__main__":
    WithCasToken.start()
