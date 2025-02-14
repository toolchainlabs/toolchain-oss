# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
import os
import platform
import subprocess
from collections.abc import Sequence
from pathlib import Path

from toolchain.util.prod.docker_client import ToolchainDockerClient

_logger = logging.getLogger(__name__)


class PexBuilder:
    _BUILDER_IMG_TAG = "pexbuild"

    def __init__(self) -> None:
        self._is_linux = platform.uname().system == "Linux"
        self._base_path = Path("dist" if self._is_linux else "dist.docker")

    @property
    def mode(self) -> str:
        return "local" if self._is_linux else "docker"

    def prepare(self) -> None:
        if self._is_linux:
            return
        client = ToolchainDockerClient()
        client.kill(f"{self._BUILDER_IMG_TAG}:latest")
        build_args = {"toolchain_user_uid": str(os.getuid())}
        client.build("builders/python/builder_image", image_tag=self._BUILDER_IMG_TAG, build_args=build_args)

    def _build_locally(self, pex_targets: Sequence[str]) -> None:
        cmd = ["./pants", "--no-dynamic-ui", "--print-stacktrace", "package"]
        cmd.extend(pex_targets)
        subprocess.check_output(cmd)

    def _build_in_docker(self, pex_targets: Sequence[str]) -> None:
        targets_str = " ".join(pex_targets)
        client = ToolchainDockerClient(ecr_login=False)
        mounts = [
            client.Mount(source=os.getcwd(), target="/toolchain/host_repo", type="bind"),
            client.Mount(source="bootstrap_cache", target="/toolchain/.cache", type="volume"),
        ]
        client.run(self._BUILDER_IMG_TAG, f"package {targets_str}", mounts)

    def _get_path(self, pex_target: str) -> Path:
        tgt_path, _, pex_file = pex_target.partition(":")
        return self._base_path / tgt_path.replace("/", ".") / f"{pex_file}.pex"

    def _move_pex_files(self, pex_paths: tuple[Path, ...]) -> tuple[Path, ...]:
        new_paths: list[Path] = []
        for path in pex_paths:
            new_paths.append(path.rename(self._base_path / path.name))
        return tuple(new_paths)

    def _build_targets(self, pex_targets: Sequence[str]) -> tuple[Path, ...]:
        pex_paths = tuple(self._get_path(target) for target in pex_targets)
        if self._is_linux:
            self._build_locally(pex_targets)
        else:
            self._build_in_docker(pex_targets)
        return self._move_pex_files(pex_paths)

    def build_targets(self, pex_targets: Sequence[str]) -> tuple[Path, ...]:
        _logger.info(f"Build {len(pex_targets)} PEX file(s) [{self.mode}]")
        return self._build_targets(pex_targets)

    def build_target(self, pex_target: str) -> Path:
        *_, pex_name = pex_target.partition(":")
        _logger.info(f"Build PEX: {pex_name} [{self.mode}]")
        return self._build_targets([pex_target])[0]
