# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

from toolchain.base.fileutil import safe_copy_file, safe_delete_file
from toolchain.config.services import BuildResult, ToolchainRustService
from toolchain.util.prod.docker_client import DockerImage, ToolchainDockerClient
from toolchain.util.prod.git_tools import get_commit_sha, get_version_tag
from toolchain.util.prod.rust_builder import RustBinaryBuilder

_logger = logging.getLogger(__name__)


class RustServiceBuilders:
    _BASE_DOCKER_PATH = Path("prod/docker/")

    def __init__(self, environment_name: str | None, push: bool = True) -> None:
        self._client = ToolchainDockerClient(ensure_repo=True)
        self._builder = RustBinaryBuilder()
        self._env_name = environment_name
        self._push = push

    def _build_image(self, binary_path: Path, service: ToolchainRustService, tag: str, commit_sha: str) -> DockerImage:
        dest_path = self._BASE_DOCKER_PATH / service.docker_path / binary_path.name
        safe_copy_file(binary_path, dest_path)
        _logger.info(f"Build rust docker image for {service.docker_path}")
        try:
            return self._client.build_and_push(
                service.docker_path,
                repo=service.ecr_repo_name,
                version_tag=tag,
                build_args=RustBinaryBuilder.BUILD_ARGS,
                push=self._push,
            )
        finally:
            safe_delete_file(dest_path)

    def build_services(self, services: Sequence[ToolchainRustService]) -> BuildResult:
        self._builder.prepare()
        version_tag = get_version_tag()
        commit_sha = get_commit_sha()
        tag = f"{self._env_name}-{version_tag}" if self._env_name else version_tag
        for service in services:
            binary = self._builder.build_target(service.binary_name)
            self._build_image(binary_path=binary, service=service, tag=tag, commit_sha=commit_sha)
        return BuildResult(revision=tag, commit_sha=commit_sha)
