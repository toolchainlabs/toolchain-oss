# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import os

from toolchain.base.fileutil import safe_copy_file
from toolchain.util.prod.docker_client import ToolchainDockerClient
from toolchain.util.prod.git_tools import get_version_tag
from toolchain.util.prod.pex_builder import PexBuilder


class LevelDBWatcherBuilder:
    _NAME = "leveldb-watcher"
    _TARGET = f"src/python/toolchain/prod/leveldb_watcher:{_NAME}"
    _DOCKER_PATH = "prod/docker/pex-wrapper/"

    def __init__(self):
        self._docker = ToolchainDockerClient(ensure_repo=True)

    def build_and_publish(self):
        builder = PexBuilder()
        builder.prepare()
        pex_path = builder.build_target(self._TARGET)
        pex_name = os.path.basename(pex_path)
        safe_copy_file(pex_path, os.path.join(self._DOCKER_PATH, pex_name))
        version_tag = get_version_tag()
        image = self._docker.build_and_push(
            self._DOCKER_PATH, repo=self._NAME, version_tag=version_tag, build_args={"PEX_FILE": pex_name}
        )
        return image.tag
