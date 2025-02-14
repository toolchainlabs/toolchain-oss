#!/usr/bin/env ./python
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
import os
from argparse import ArgumentParser
from pathlib import Path

from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.util.prod.docker_client import ToolchainDockerClient

_logger = logging.getLogger(__name__)


class RustBinaryBuilder:
    _BUILDER_IMG_TAG = "rust_builder"

    BUILD_ARGS = {
        "rust_server_base_image": "debian:buster-20220509-slim@sha256:69f5980eb8901ca6829d36f2aea008f3cdb39a23aec23511054a6801244cbaa5",
        "rust_version": "1.68.0",
    }

    def prepare(self) -> None:
        client = ToolchainDockerClient()
        client.kill(f"{self._BUILDER_IMG_TAG}:latest")
        client.build("builders/rust", image_tag=self._BUILDER_IMG_TAG, build_args=self.BUILD_ARGS)

    def build_target(self, target: str) -> Path:
        dist_dir = Path("dist/")
        dist_dir.mkdir(exist_ok=True)
        client = ToolchainDockerClient(ecr_login=False)
        mounts = [
            client.Mount(source=os.getcwd(), target="/toolchain/host_repo", type="bind"),
            client.Mount(
                source="rust-builder-target-dir", target="/toolchain/host_repo/src/rust/target", type="volume"
            ),
            # Bind the cache subdirectories of /usr/local/cargo.
            # Note: We cannot bind /usr/local/cargo since that would bind /usr/local/cargo/bin which has
            # platform-specific binaries which could differ between host and container.
            client.Mount(
                source=os.path.expanduser("~/.cargo/git"),
                target="/usr/local/cargo/git",
                type="bind",
            ),
            client.Mount(
                source=os.path.expanduser("~/.cargo/registry"),
                target="/usr/local/cargo/registry",
                type="bind",
            ),
        ]
        _logger.info(f"Build rust binary in docker: {target}")
        client.run(self._BUILDER_IMG_TAG, cmd=target, mounts=mounts)
        return dist_dir / target


class RustBinaryBuilderScript(ToolchainBinary):
    def run(self) -> int:
        builder = RustBinaryBuilder()
        builder.prepare()

        target = self.cmdline_args.target
        path = builder.build_target(target)
        _logger.info(f"Wrote {target} binary to {path}")
        return 0

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        parser.add_argument(
            "target",
            help="The Rust target to build, e.g. `proxy_server` or `worker`. Use `_` instead of `-`. ",
        )


if __name__ == "__main__":
    RustBinaryBuilderScript.start()
