#!/usr/bin/env ./python
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
from pathlib import Path

import tomlkit
from ruamel.yaml import YAML

from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.util.prod.rust_builder import RustBinaryBuilder

logger = logging.getLogger(__name__)


class CheckRustVersions(ToolchainBinary):
    description = "Check that rust versions are consistent across the repo"

    def _get_rust_version_from_gha(sefl, gha_file: str, job_name: str):
        gha_workflow = YAML().load(Path(f".github/workflows/{gha_file}.yml").read_text())
        steps = gha_workflow["jobs"][job_name]["steps"]
        rust_tc_step = next(step for step in steps if step.get("uses", "").startswith("actions-rs/toolchain@"))
        rust_ci_version = str(rust_tc_step["with"]["toolchain"])
        return rust_ci_version

    def run(self) -> int:
        rust_toolchain_version = tomlkit.parse(Path("rust-toolchain.toml").read_text())["toolchain"]["channel"]  # type: ignore[index]
        rust_ci_version = self._get_rust_version_from_gha("rust-ci", "build_and_test")
        pubish_remote_exec_worker_version = self._get_rust_version_from_gha(
            "buildbox-release", "build-and-publish-release"
        )
        builder_version = RustBinaryBuilder.BUILD_ARGS["rust_version"]
        if builder_version == rust_ci_version == rust_toolchain_version == pubish_remote_exec_worker_version:
            return 0
        logger.error(
            f"Rust toolchain version inconsistent across the repo, see {type(self).__name__} to see where versions are defined."
        )
        logger.error(
            f"RustBinaryBuilder: {builder_version} rust-toolchain.toml: {rust_toolchain_version} rust-ci.yml: {rust_ci_version}"
        )
        return -1


if __name__ == "__main__":
    CheckRustVersions.start()
