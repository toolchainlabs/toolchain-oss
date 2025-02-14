# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from toolchain.base.fileutil import safe_copy_file, safe_delete_file
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.config.services import BuildResult, ToolchainWorkflowService
from toolchain.util.prod.docker_client import DockerImage, ToolchainDockerClient
from toolchain.util.prod.git_tools import get_commit_sha, get_version_tag
from toolchain.util.prod.pex_builder import PexBuilder

_logger = logging.getLogger(__name__)


class WorkflowServiceBuilder:
    _WORKFLOW_PEX_PATH = Path("prod/docker/django/workflow/")

    def __init__(self, environment_name: str | None, max_workers: int | None = None, push: bool = True) -> None:
        self._client = ToolchainDockerClient(ensure_repo=True)
        self._pex_builder = PexBuilder()
        self._max_worker = max_workers or 3
        self._env_name = environment_name
        self._push = push

    def _build_pex_files(
        self, services: Sequence[ToolchainWorkflowService]
    ) -> dict[ToolchainWorkflowService, tuple[Path, Path | None]]:
        worker_targets = [service.worker_pants_target for service in services]
        worker_maintenance_targets = [service.worker_maintenance_pants_target for service in services]
        all_paths = self._pex_builder.build_targets(worker_targets + worker_maintenance_targets)
        worker_paths = all_paths[: len(worker_targets)]
        maintenance_paths = all_paths[len(worker_targets) :]
        if len(worker_paths) != len(services):
            raise ToolchainAssertion("Unexpected pex build results")
        return {service: (worker_paths[index], maintenance_paths[index]) for index, service in enumerate(services)}

    def _build_worker(
        self, pex_path: Path, service_dir: str, ecr_repo: str, manage_py_module: str, tag: str, commit_sha: str
    ) -> DockerImage:
        pex_name = pex_path.name
        dest_pex = self._WORKFLOW_PEX_PATH.joinpath(pex_name)
        safe_copy_file(pex_path.as_posix(), dest_pex)
        _logger.info(f"Build workflow worker docker image for {service_dir} ECR repo: {ecr_repo}")
        try:
            return self._client.build_and_push(
                "django/workflow",
                repo=ecr_repo,
                version_tag=tag,
                build_args={
                    "PEX_FILE": pex_name,
                    "COMMIT_SHA": commit_sha,
                    "MANAGE_PY_MODULE": manage_py_module,
                },
                push=self._push,
            )
        finally:
            safe_delete_file(dest_pex)

    def build_services(self, services: Sequence[ToolchainWorkflowService]) -> BuildResult:
        self._pex_builder.prepare()
        version_tag = get_version_tag()
        commit_sha = get_commit_sha()
        tag = f"{self._env_name}-{version_tag}" if self._env_name else version_tag
        service_map = self._build_pex_files(services)
        asyncio.run(self._build_images_async(service_map, tag, commit_sha))
        return BuildResult(revision=tag, commit_sha=commit_sha)

    async def _build_images_async(
        self, service_map: dict[ToolchainWorkflowService, tuple[Path, Path | None]], tag: str, commit_sha: str
    ) -> None:
        futures = []
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=self._max_worker) as pool:
            for service, pex_paths in service_map.items():
                manage_py_module = service.module("manage")
                worker, maintenance = pex_paths
                fut = loop.run_in_executor(
                    pool,
                    self._build_worker,
                    worker,
                    service.service_dir,
                    service.worker_ecr_repo_name,
                    manage_py_module,
                    tag,
                    commit_sha,
                )

                futures.append(fut)
                if maintenance:
                    fut = loop.run_in_executor(
                        pool,
                        self._build_worker,
                        maintenance,
                        service.service_dir,
                        service.maintenance_ecr_repo_name,
                        manage_py_module,
                        tag,
                        commit_sha,
                    )
                    futures.append(fut)
        await asyncio.gather(*futures)
