# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import asyncio
import logging
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from toolchain.base.fileutil import safe_copy_file, safe_delete_file
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.config.services import BuildResult, ToolchainGunicornService
from toolchain.util.prod.docker_client import DockerImage, ToolchainDockerClient
from toolchain.util.prod.git_tools import get_commit_sha, get_version_tag
from toolchain.util.prod.pex_builder import PexBuilder

_logger = logging.getLogger(__name__)


class GunicornAppBuilder:
    _GUNICORN_PEX_PATH = Path("prod/docker/django/gunicorn/")

    def __init__(self, environment_name: Optional[str], max_workers: Optional[int] = None, push: bool = True) -> None:
        self._client = ToolchainDockerClient()
        self._pex_builder = PexBuilder()
        self._max_worker = max_workers or 3
        self._env_name = environment_name
        self._push = push

    def _build_pex_files(self, services: Sequence[ToolchainGunicornService]) -> dict[ToolchainGunicornService, Path]:
        targets = [service.pants_target for service in services]
        paths = self._pex_builder.build_targets(targets)
        if len(paths) != len(services):
            raise ToolchainAssertion("Unexpected pex build results")
        return {services[index]: path for index, path in enumerate(paths)}

    def _build_gunicorn(
        self, pex_path: Path, service: ToolchainGunicornService, tag: str, commit_sha: str
    ) -> DockerImage:
        pex_name = pex_path.name
        dest_pex = self._GUNICORN_PEX_PATH.joinpath(pex_name)
        safe_copy_file(pex_path.as_posix(), dest_pex)
        _logger.info(f"Build gunicorn docker image for {service.service_dir}")
        build_args = {
            "PEX_FILE": pex_name,
            "MANAGE_PY_MODULE": service.module("manage"),
            "COMMIT_SHA": commit_sha,
            "COLLECT_STATIC": "1" if service.has_static_files else "0",
        }

        try:
            return self._client.build_and_push(
                "django/gunicorn", repo=service.ecr_repo_name, version_tag=tag, build_args=build_args, push=self._push
            )
        finally:
            safe_delete_file(dest_pex)

    def build_services(self, services: Sequence[ToolchainGunicornService]) -> BuildResult:
        self._pex_builder.prepare()
        version_tag = get_version_tag()
        commit_sha = get_commit_sha()
        tag = f"{self._env_name}-{version_tag}" if self._env_name else version_tag
        service_map = self._build_pex_files(services)
        asyncio.run(self._build_images_async(service_map, tag, commit_sha))
        return BuildResult(revision=tag, commit_sha=commit_sha)

    async def _build_images_async(
        self, service_map: dict[ToolchainGunicornService, Path], tag: str, commit_sha: str
    ) -> None:
        futures = []
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=self._max_worker) as pool:
            for service, pex_path in service_map.items():
                fut = loop.run_in_executor(pool, self._build_gunicorn, pex_path, service, tag, commit_sha)
                futures.append(fut)
        await asyncio.gather(*futures)
