# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.constants import ToolchainEnv
from toolchain.util.elasticsearch.config import ElasticSearchConfig


def test_lambda_dev_config():
    es_config = ElasticSearchConfig.for_lambda(es_host="pretzel.dev.local")
    assert es_config.get_es_hosts() == [{"host": "pretzel.dev.local", "port": 443}]
    assert es_config.host == "pretzel.dev.local"
    assert es_config.needs_auth is True


def test_k8s_dev_config():
    es_config = ElasticSearchConfig.for_env(
        toolchain_env=ToolchainEnv.DEV, is_k8s=True, config={"ELASTICSEARCH_HOST": "apt5e.local.dev"}
    )
    assert es_config.get_es_hosts() == [{"host": "apt5e.local.dev", "port": 443}]
    assert es_config.host == "apt5e.local.dev"
    assert es_config.needs_auth is True


def test_k8s_prod_config():
    es_config = ElasticSearchConfig.for_env(
        toolchain_env=ToolchainEnv.PROD, is_k8s=True, config={"ELASTICSEARCH_HOST": "puffy.shirt.local.dev"}
    )
    assert es_config.get_es_hosts() == [{"host": "puffy.shirt.local.dev", "port": 443}]
    assert es_config.host == "puffy.shirt.local.dev"
    assert es_config.needs_auth is True


def test_local_dev_config():
    es_config = ElasticSearchConfig.for_env(toolchain_env=ToolchainEnv.DEV, is_k8s=False, config={})
    assert es_config.get_es_hosts() == [{"host": "localhost", "port": 9200}]
    assert es_config.host == "localhost"
    assert es_config.needs_auth is False


def test_no_host():
    with pytest.raises(ToolchainAssertion):
        ElasticSearchConfig.for_lambda(es_host="")

    with pytest.raises(ToolchainAssertion):
        ElasticSearchConfig.for_env(toolchain_env=ToolchainEnv.DEV, is_k8s=True, config={})


def test_not_supported():
    with pytest.raises(ToolchainAssertion, match="Only prod & dev environments are supported."):
        ElasticSearchConfig.for_env(toolchain_env=ToolchainEnv.COLLECTSTATIC, is_k8s=False, config={})

    with pytest.raises(ToolchainAssertion, match="Only prod & dev environments are supported."):
        ElasticSearchConfig.for_env(toolchain_env=ToolchainEnv.TEST, is_k8s=False, config={})
