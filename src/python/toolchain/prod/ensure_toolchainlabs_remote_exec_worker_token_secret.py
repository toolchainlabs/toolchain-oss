#!/usr/bin/env ./python
# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from argparse import ArgumentParser, Namespace

from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.kubernetes.constants import KubernetesCluster
from toolchain.util.secret.secrets_accessor import AWSSecretsAccessor, KubernetesSecretsAccessor

logger = logging.getLogger(__name__)


class EnsureRemoteExecSecret(ToolchainBinary):
    description = "Ensure that the remote execution worker token for toolchainlabs is stored in the dev cluster"
    _SECRET_NAME = "toolchainlabs-remote-exec-worker-token"
    _NAMESPACE = "remote-exec"

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._aws_region = cmd_args.aws_region

    def run(self) -> int:
        remote_worker_token_dict = AWSSecretsAccessor(self._aws_region).get_json_secret_or_raise(self._SECRET_NAME)
        accessors = KubernetesSecretsAccessor.create(cluster=KubernetesCluster.DEV, namespace=self._NAMESPACE)
        accessors.set_secret(self._SECRET_NAME, remote_worker_token_dict)
        return 0

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)


if __name__ == "__main__":
    EnsureRemoteExecSecret.start()
