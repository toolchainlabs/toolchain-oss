# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.util.prod.docker_client import ToolchainDockerClient
from toolchain.util.prod.git_tools import get_commit_sha, get_version_tag


class AwsESProxyBuilder:
    _NAME = "aws-es-proxy"
    _DOCKER_PATH = "src/go/src/aws-es-proxy"

    def __init__(self):
        self._docker = ToolchainDockerClient(ensure_repo=True)

    def build_and_publish(self):
        version_tag = get_version_tag()
        build_args = {"GIT_COMMIT": get_commit_sha()}
        image = self._docker.build_and_push(
            self._DOCKER_PATH, repo=self._NAME, version_tag=version_tag, build_args=build_args
        )
        return image.tag
