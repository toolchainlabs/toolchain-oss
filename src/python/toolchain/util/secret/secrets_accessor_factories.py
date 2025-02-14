# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.constants import ToolchainEnv
from toolchain.kubernetes.constants import KubernetesCluster
from toolchain.util.secret.secrets_accessor import (
    DummySecretsAccessor,
    KubernetesSecretsAccessor,
    KubernetesVolumeSecretsReader,
    LocalSecretsAccessor,
    SecretsReader,
    TrackingSecretsReader,
)


def kubernetes_api_secrets_reader(namespace: str, cluster: KubernetesCluster) -> SecretsReader:
    return TrackingSecretsReader(KubernetesSecretsAccessor.create_rotatable(namespace=namespace, cluster=cluster))


def local_secrets_reader(secrets_dir: str | None = None) -> SecretsReader:
    return TrackingSecretsReader(LocalSecretsAccessor.create_rotatable(secrets_dir=secrets_dir))


def kubernetes_secrets_reader() -> SecretsReader:
    # A service running on Kubernetes can access secrets via the mounted secret volume.
    return TrackingSecretsReader(KubernetesVolumeSecretsReader.create_rotatable())


def test_secrets_reader() -> SecretsReader:
    return TrackingSecretsReader(DummySecretsAccessor.create_rotatable())


def get_secrets_reader(
    *,
    toolchain_env: ToolchainEnv,
    is_k8s: bool,
    use_remote_dbs: bool,
    k8s_namespace: str,
    secrets_dir: str | None = None,
) -> SecretsReader:
    if is_k8s:
        return kubernetes_secrets_reader()
    if toolchain_env.is_prod:  # type: ignore[attr-defined]
        raise ToolchainAssertion("PROD env is only supported when running in kubernetes.")
    if use_remote_dbs:
        return kubernetes_api_secrets_reader(namespace=k8s_namespace, cluster=KubernetesCluster.DEV)
    return local_secrets_reader(secrets_dir=secrets_dir)
