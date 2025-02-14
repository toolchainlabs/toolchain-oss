# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.constants import ToolchainEnv
from toolchain.prod.e2e_tests.helpers import wait_for_host


def pytest_addoption(parser):
    parser.addoption("--toolchain_env", action="store", default=ToolchainEnv.PROD.value, help="toolchain env name")  # type: ignore[attr-defined]
    parser.addoption("--namespace", action="store", default="prod", help="Kubernetes namespace")


_HOSTS_MAP = {
    (ToolchainEnv.PROD.value, "prod"): "toolchain.com",  # type: ignore[attr-defined]
    (ToolchainEnv.PROD.value, "staging"): "staging.toolchain.com",  # type: ignore[attr-defined]
    ToolchainEnv.DEV.value: "infosite",  # type: ignore[attr-defined]
}


@pytest.fixture(scope="session")
def tc_env(request) -> ToolchainEnv:
    ns = request.config.getoption("namespace")
    toolchain_env = ToolchainEnv(request.config.getoption("toolchain_env"))
    if ns:
        toolchain_env = toolchain_env.namespaced(ns, is_local=False)  # type: ignore[attr-defined]
    return toolchain_env


@pytest.fixture(scope="session")
def host(tc_env: ToolchainEnv) -> str:
    host_name = _HOSTS_MAP.get((tc_env.value, tc_env.namespace)) or _HOSTS_MAP.get(tc_env.value)  # type: ignore[attr-defined]
    if not host_name:
        pytest.fail(f"Failed to resolve host name for env: {tc_env}")
    if tc_env.is_prod:  # type: ignore[attr-defined]
        # In prod (mostly staging) we need to wait for the ALB to be provisioned and for the DNS to be updated
        # This can take a few minutes.
        wait_for_host(host_name)
    return host_name


@pytest.fixture(scope="session")
def is_dev(tc_env: ToolchainEnv) -> bool:
    return tc_env.is_dev  # type: ignore[attr-defined]
