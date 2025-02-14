# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import os
from pathlib import Path

from toolchain.base.fileutil import safe_copy_file, safe_delete_file
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.util.prod.docker_client import ToolchainDockerClient
from toolchain.util.prod.git_tools import get_version_tag
from toolchain.util.prod.pex_builder import PexBuilder


class PexWrapperBuilder:
    _BASE_DOCKER_PATH = Path("prod/docker")
    _DEFAULT_DOCKER_PATH = _BASE_DOCKER_PATH / "pex-wrapper"

    def __init__(
        self,
        *,
        pants_target: str,
        ecr_repo: str | None = None,
        docker_path: str | None = None,
    ) -> None:
        self._docker = ToolchainDockerClient(ensure_repo=True)
        target_name = pants_target.partition(":")[-1]
        if not target_name:
            raise ToolchainAssertion(f"Invalid pants/pex target name: {pants_target}")
        self._docker_path = (self._BASE_DOCKER_PATH / docker_path) if docker_path else self._DEFAULT_DOCKER_PATH
        self._target = pants_target
        self._repo = ecr_repo or target_name

    def build_and_publish(self, env_name: str | None = None) -> str:
        builder = PexBuilder()
        builder.prepare()
        pex_path = builder.build_target(self._target)
        pex_name = os.path.basename(pex_path)
        version_tag = get_version_tag()
        tag = f"{env_name}-{version_tag}" if env_name else version_tag
        dest_pex = self._docker_path / pex_name
        safe_copy_file(pex_path, dest_pex)
        try:
            image = self._docker.build_and_push(
                self._docker_path.as_posix(),
                repo=self._repo,
                version_tag=tag,
                build_args={"PEX_FILE": pex_name},
            )
        finally:
            safe_delete_file(dest_pex)

        return image.tag
