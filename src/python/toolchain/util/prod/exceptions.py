# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.kubernetes.constants import KubernetesCluster


class NotConnectedToClusterError(ToolchainAssertion):
    def __init__(self, cluster: KubernetesCluster) -> None:
        super().__init__(
            f"Not connected to cluster `{cluster.value}`. To connect, run: ./prod/kubernetes/kubectl_setup.sh {cluster.value}"
        )
