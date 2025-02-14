# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.constants import ToolchainEnv


def test_toolchain_dev_env():
    env = ToolchainEnv("toolchain_dev").namespaced("jerry", is_local=False)
    assert env.is_dev is True
    assert env.is_prod_or_dev is True
    assert env.is_prod is False
    assert env.is_collect_static is False
    assert env.get_env_name() == "jerry"
    env = ToolchainEnv("toolchain_dev").namespaced(namespace="george", is_local=True)
    assert env.get_env_name() == "local-george"


def test_toolchain_prod_env():
    env = ToolchainEnv("toolchain_prod")
    assert env.is_dev is False
    assert env.is_prod_or_dev is True
    assert env.is_prod is True
    assert env.is_collect_static is False
    assert env.get_env_name() == "prod"


def test_toolchain_collect_static_env():
    env = ToolchainEnv("toolchain_collectstatic")
    assert env.is_dev is False
    assert env.is_prod_or_dev is False
    assert env.is_prod is False
    assert env.is_collect_static is True
    assert env.get_env_name() == "collectstatic"


def test_toolchain_env_invalid():
    with pytest.raises(TypeError, match="missing 1 required positional argument: 'value'"):
        ToolchainEnv()
    with pytest.raises(ValueError, match="'toolchain_jerry' is not a valid ToolchainEnv"):
        ToolchainEnv("toolchain_jerry")
    with pytest.raises(ValueError, match="'' is not a valid ToolchainEnv"):
        ToolchainEnv("")
    with pytest.raises(ValueError, match="None is not a valid ToolchainEnv"):
        ToolchainEnv(None)
    with pytest.raises(ValueError, match="0 is not a valid ToolchainEnv"):
        ToolchainEnv(0)
    with pytest.raises(ValueError, match="False is not a valid ToolchainEnv"):
        ToolchainEnv(False)
