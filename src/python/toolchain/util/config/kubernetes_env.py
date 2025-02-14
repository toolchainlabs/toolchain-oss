# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from toolchain.constants import ToolchainEnv
from toolchain.kubernetes.constants import KubernetesCluster
from toolchain.util.config.app_config import AppConfig


class KubernetesEnv:
    @classmethod
    def from_config(cls, config: AppConfig) -> KubernetesEnv:
        return cls(config)

    @classmethod
    def from_env(cls) -> KubernetesEnv:
        return cls.from_config(AppConfig.from_env())

    def __init__(self, config: AppConfig) -> None:
        is_prod = config.get("TOOLCHAIN_ENV") == ToolchainEnv.PROD.value  # type: ignore[attr-defined]
        self._config = config
        self._cluster = KubernetesCluster.PROD if is_prod else KubernetesCluster.DEV

    @property
    def cluster(self) -> KubernetesCluster:
        return self._cluster

    @property
    def namespace(self) -> str:
        return self._get_str("K8S_POD_NAMESPACE")

    @property
    def pod_ip(self) -> str:
        return self._get_str("K8S_POD_IP")

    @property
    def pod_name(self) -> str:
        return self._get_str("K8S_NODE_NAME")

    @property
    def is_running_in_kubernetes(self) -> bool:
        return self._config.get("K8S_POD_NAMESPACE") is not None

    def _get_str(self, key: str) -> str:
        return self._config[key]  # type: ignore[return-value]
