# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import docker
from docker import types
from docker.errors import BuildError, ContainerError, NotFound
from docker.models.images import Image
from requests.exceptions import RequestException

from toolchain.aws.ecr import ECR
from toolchain.base.toolchain_error import ToolchainAssertion, ToolchainError

_logger = logging.getLogger(__name__)

DockerMounts = Sequence[types.Mount]


class DockerNotRunningError(ToolchainError):
    """Raised if we can't talk to the Docker daemon."""


@dataclass(frozen=True)
class DockerImage:
    repo: str | None
    tag: str
    sha256: str


class ToolchainDockerClient:
    _AWS_REGION = "us-east-1"
    _IMAGE_REGISTRY = f"283194185447.dkr.ecr.{_AWS_REGION}.amazonaws.com/"
    _BASE_PATH = Path("prod/docker")

    # This way callers don't have to import stuff directly from docker
    Mount = types.Mount

    def __init__(self, ensure_repo: bool = False, ecr_login: bool = True):
        self._client = docker.DockerClient.from_env()
        try:
            self._client.info()  # ping docker daemon
        except (FileNotFoundError, RequestException):
            raise DockerNotRunningError("Docker is not running")
        self._ensure_repo = ensure_repo
        self._auth: dict[str, str] | None = None
        self._ecr = ECR(self._AWS_REGION)
        if ecr_login:
            self.ecr_login()

    def kill(self, image_tag: str) -> None:
        for container in self._client.containers.list():
            image = container.image
            if image_tag in image.tags:
                _logger.info(f"Killing running container: {container.name} - {image!r}")
                container.kill()

    def build(self, dockerfile_path: str, image_tag: str, build_args: dict | None = None) -> tuple[Image, str]:
        full_path = Path(dockerfile_path)
        if not full_path.exists():
            full_path = self._BASE_PATH / dockerfile_path
        if full_path.is_dir():
            full_path = full_path / "Dockerfile"
        _logger.info(f"Build {full_path} tag={image_tag}")
        try:
            image, docker_logs = self._client.images.build(
                dockerfile=full_path.name,
                platform="linux/amd64",
                path=full_path.parent.as_posix(),
                tag=image_tag,
                buildargs=build_args,
            )
        except BuildError as error:
            build_log = "".join(line["stream"] for line in error.build_log if "stream" in line)
            _logger.error(f"{build_log} \n\n {error.msg}")
            raise ToolchainAssertion(f"Failed to build {full_path} tag={image_tag} with {build_args}")
        _logger.debug("".join(lg.get("stream") or lg.get("status") or lg["aux"]["ID"] for lg in docker_logs))
        return image, image_tag

    def build_and_push(
        self,
        dockerfile_path: str,
        repo: str,
        version_tag: str,
        build_args: dict | None = None,
        push: bool = True,
    ) -> DockerImage:
        start = time.time()
        image_tag = f"{self._IMAGE_REGISTRY}{repo}:{version_tag}"
        image, image_tag = self.build(dockerfile_path, image_tag=image_tag, build_args=build_args)
        if push:
            self._push_to_ecr(version_tag=version_tag, repo=repo)
        took = time.time() - start
        if push:
            _logger.info(f"Built & pushed {repo}:{version_tag} in {took:.2f} seconds.")
        else:
            _logger.info(f"Built locally {repo}:{version_tag} in {took:.2f} seconds.")
        return DockerImage(repo=repo, tag=image_tag, sha256=image.id)

    def _create_volumes(self, mounts: DockerMounts) -> None:
        for mount in mounts:
            if mount["Type"] != "volume":
                continue
            vol_name = mount["Source"]
            try:
                self._client.volumes.get(vol_name)
            except NotFound:
                _logger.info(f"create volume: {vol_name}")
                self._client.volumes.create(vol_name)

    def run(
        self, image_tag: str, cmd: str | None, mounts: DockerMounts, env_variables: dict[str, str] | None = None
    ) -> None:
        self._create_volumes(mounts)
        try:
            output = self._client.containers.run(
                image=f"{image_tag}:latest", command=cmd, mounts=mounts, remove=True, environment=env_variables
            )
        except ContainerError as error:
            _logger.exception(error.stderr.decode())
            raise ToolchainAssertion("Docker Run error")
        _logger.debug(output.decode())

    def ecr_login(self) -> None:
        docker_auth = self._ecr.get_auth_data()
        response = self._client.login(
            docker_auth.username, password=docker_auth.password, registry=docker_auth.registry, reauth=True
        )
        if response.get("Status") != "Login Succeeded":
            raise ToolchainAssertion("Failed to login to ECR")
        self._auth = docker_auth.to_auth_dict()

    def _push_to_ecr(self, version_tag: str, repo: str) -> None:
        if self._ensure_repo:
            self._ecr.ensure_repository(repo)
        _logger.debug(f"Logged in to {self._IMAGE_REGISTRY}, pushing to {repo} version: {version_tag}")
        full_repo = f"{self._IMAGE_REGISTRY}{repo}"
        response_lines = self._client.images.push(
            repository=full_repo, tag=version_tag, auth_config=self._auth
        ).splitlines()
        for line in response_lines:
            _logger.debug(line)
        push_status = {}
        for line in response_lines:
            push_status.update(json.loads(line))
        error = push_status.get("error") or push_status.get("errorDetail")
        if error:
            _logger.warning(f"Failed: {error}")
            raise ToolchainAssertion(f"Push ro ECR failed. {error}")
        _logger.debug(f"Pushed to ECR {repo} version: {version_tag}")
