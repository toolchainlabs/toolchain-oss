# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from pathlib import Path
from unittest import mock

import pytest

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.constants import ToolchainEnv
from toolchain.util.secret.secrets_accessor import (
    KubernetesSecretsAccessor,
    KubernetesVolumeSecretsReader,
    LocalSecretsAccessor,
    RotatableSecretsAccessor,
    TrackingSecretsReader,
)
from toolchain.util.secret.secrets_accessor_factories import get_secrets_reader


@mock.patch("toolchain.kubernetes.kubernetes_api.kubernetes.config.load_kube_config")
@mock.patch("toolchain.kubernetes.kubernetes_api.kubernetes.client.CoreV1Api")
def test_get_secrets_reader_dev_local_with_remote_dbs(mock_load_config, mock_api):
    reader = get_secrets_reader(
        toolchain_env=ToolchainEnv.DEV, is_k8s=False, use_remote_dbs=True, k8s_namespace="jerry"
    )
    assert isinstance(reader, TrackingSecretsReader)
    assert isinstance(reader._reader, RotatableSecretsAccessor)
    assert isinstance(reader._reader._accessor, KubernetesSecretsAccessor)
    assert reader._reader._accessor._kubernetes_secret_api.namespace == "jerry"


def test_get_secrets_reader_dev_local(tmp_path: Path) -> None:
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir(parents=True, exist_ok=True)
    reader = get_secrets_reader(
        toolchain_env=ToolchainEnv.DEV,  # type: ignore
        is_k8s=False,
        use_remote_dbs=False,
        k8s_namespace="jerry",
        secrets_dir=secrets_dir.as_posix(),
    )
    assert isinstance(reader, TrackingSecretsReader)
    assert isinstance(reader._reader, RotatableSecretsAccessor)
    assert isinstance(reader._reader._accessor, LocalSecretsAccessor)


def test_get_secrets_reader_k8s() -> None:
    reader = get_secrets_reader(
        toolchain_env=ToolchainEnv.DEV,  # type: ignore
        is_k8s=True,
        use_remote_dbs=False,
        k8s_namespace="jerry",
    )
    assert isinstance(reader, TrackingSecretsReader)
    assert isinstance(reader._reader, RotatableSecretsAccessor)
    assert isinstance(reader._reader._accessor, KubernetesVolumeSecretsReader)


@pytest.mark.parametrize("tc_env", [ToolchainEnv.DEV, ToolchainEnv.COLLECTSTATIC, ToolchainEnv.TEST])  # type: ignore[attr-defined]
def test_get_secrets_reader(tc_env) -> None:
    reader = get_secrets_reader(toolchain_env=tc_env, is_k8s=False, use_remote_dbs=False, k8s_namespace="jerry")
    assert isinstance(reader, TrackingSecretsReader)
    assert isinstance(reader._reader, RotatableSecretsAccessor)
    assert isinstance(reader._reader._accessor, LocalSecretsAccessor)


def test_get_secrets_reader_invalid_config() -> None:
    with pytest.raises(ToolchainAssertion, match="PROD env is only supported when running in kubernetes"):
        get_secrets_reader(toolchain_env=ToolchainEnv.PROD, is_k8s=False, use_remote_dbs=False, k8s_namespace="jerry")  # type: ignore [attr-defined]
