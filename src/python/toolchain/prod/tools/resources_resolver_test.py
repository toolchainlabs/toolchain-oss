# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from typing import Union

import pytest

from toolchain.aws.test_utils.mock_es_client import mock_es_client
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.constants import ToolchainEnv
from toolchain.kubernetes.constants import KubernetesCluster
from toolchain.prod.tools.resources_resolver import resolve_resources

ChartValues = dict[str, Union[str, dict]]

_ES_DOMAINS = [
    {
        "name": "jerry",
        "arn": "no-soup-for-you",
        "endpoint": "jambalaya",
        "tags": {"env": "toolchain_prod", "app": "buildsense-api"},
    },
    {
        "name": "gold-jerry",
        "arn": "i-was-in-a-pool",
        "endpoint": "the-baby",
        "tags": {"env": "toolchain_dev", "app": "buildsense-api"},
    },
]


@mock_es_client(_ES_DOMAINS)
@pytest.mark.parametrize("service", ["buildsense-workflow", "buildsense-api"])
def test_resolve_buildsense_dev(service: str) -> None:
    chart_values: ChartValues = {"extra_config": {"INFLUXDB_CONFIG": {"host": None}}}
    resolve_resources(service=service, aws_region="us-east-44", cluster=KubernetesCluster.DEV, toolchain_env=ToolchainEnv.DEV, namespace="ovaltine", chart_values=chart_values)  # type: ignore[attr-defined]
    assert chart_values == {
        "extra_config": {
            "BUILDSENSE_ELASTICSEARCH_HOST": "the-baby",
            "BUILDSENSE_BUCKET": "staging.buildstats-dev.us-east-1.toolchain.com",
            "INFLUXDB_CONFIG": {"host": "influxdb.ovaltine.svc.cluster.local"},
        }
    }


@mock_es_client(_ES_DOMAINS)
@pytest.mark.parametrize("service", ["buildsense-workflow", "buildsense-api"])
def test_resolve_buildsense_prod(service: str) -> None:
    chart_values: ChartValues = {"extra_config": {"INFLUXDB_CONFIG": {"host": None}}}
    resolve_resources(service=service, aws_region="us-east-44", cluster=KubernetesCluster.PROD, toolchain_env=ToolchainEnv.PROD, namespace="ovaltine", chart_values=chart_values)  # type: ignore[attr-defined]
    assert chart_values == {
        "extra_config": {
            "BUILDSENSE_ELASTICSEARCH_HOST": "jambalaya",
            "BUILDSENSE_BUCKET": "builds.buildsense.us-east-1.toolchain.com",
            "INFLUXDB_CONFIG": {"host": "influxdb.prod.svc.cluster.local"},
        }
    }


@mock_es_client(_ES_DOMAINS)
@pytest.mark.parametrize("service", ["buildsense-workflow", "buildsense-api"])
def test_resolve_buildsense_missing_es_domains(service: str) -> None:
    chart_values: ChartValues = {"extra_config": {}}
    with pytest.raises(ToolchainAssertion, match="ES Domain with tags .* not found."):
        resolve_resources(service=service, aws_region="us-east-44", cluster=KubernetesCluster.DEV, toolchain_env=ToolchainEnv.TEST, namespace="ovaltine", chart_values=chart_values)  # type: ignore[attr-defined]
