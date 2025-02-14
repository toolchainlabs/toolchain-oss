# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.constants import ToolchainEnv


def pytest_addoption(parser):
    parser.addoption("--toolchain_env", action="store", default=ToolchainEnv.PROD.value, help="toolchain env name")  # type: ignore[attr-defined]
    parser.addoption("--namespace", action="store", default="prod", help="Kubernetes namespace")


_HOSTS_MAP = {
    (ToolchainEnv.PROD.value, "prod"): "webhooks.toolchain.com",  # type: ignore[attr-defined]
    (ToolchainEnv.PROD.value, "staging"): "staging.webhooks.toolchain.com",  # type: ignore[attr-defined]
    ToolchainEnv.DEV.value: "webhooks",  # type: ignore[attr-defined]
    # ToolchainEnv.DEV.value: "localhost:9080",  # type: ignore[attr-defined]
}


@pytest.fixture(scope="session")
def tc_env(request):
    ns = request.config.getoption("namespace")
    toolchain_env = ToolchainEnv(request.config.getoption("toolchain_env"))
    if ns:
        toolchain_env = toolchain_env.namespaced(ns, is_local=False)
    return toolchain_env


@pytest.fixture(scope="session")
def host(tc_env):
    return _HOSTS_MAP.get((tc_env.value, tc_env.namespace)) or _HOSTS_MAP.get(tc_env.value)  # type: ignore[attr-defined]
