# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from pathlib import Path

import pytest
from moto import mock_secretsmanager, mock_sts

from toolchain.aws.test_utils.mock_es_client import mock_es_client
from toolchain.aws.test_utils.secrets import create_fake_secret
from toolchain.kubernetes.constants import KubernetesCluster
from toolchain.prod.installs.install_logging_prod import ComponentsVersions, InstallLoggingProd
from toolchain.prod.installs.tests_helpers import FakeKubernetesCluster
from toolchain.util.prod.helm_charts import HelmChart

ES_DOMAINS = [
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
        "tags": {"env": "toolchain_prod", "app": "logging"},
    },
]


class TestInstallLoggingProd:
    _FAKE_REGION = "ap-northeast-1"
    _FAKE_CLUSTERS = {
        KubernetesCluster.PROD: "yada-yada",
        KubernetesCluster.REMOTING: "festivus",
    }

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_secretsmanager(), mock_sts():
            yield

    def _create_installer(self, cluster: KubernetesCluster):
        fake_cluster = self._FAKE_CLUSTERS[cluster]
        cfg = InstallLoggingProd._CLUSTER_CONFIG[cluster]
        InstallLoggingProd._CLUSTER_CONFIG[FakeKubernetesCluster(fake_cluster)] = cfg  # type: ignore[index]
        installer = InstallLoggingProd.create_for_args(
            aws_region=self._FAKE_REGION, version=None, dry_run=True, cluster=fake_cluster
        )
        # Sanity checks.
        assert installer._helm._HELM_EXECUTABLE == "no-op"
        assert installer._helm.cluster_name == fake_cluster
        return installer

    def _create_secret(self):
        create_fake_secret(
            region=self._FAKE_REGION, name="prod/monitoring", secret={"slack-webhook": "https://fake.chat.puffy.local"}
        )

    def _assert_fluent_bit_cfg(self, flunetbit_cfg: dict, log_name: str, cluster_name: str) -> None:
        es_host = "the-baby"
        assert flunetbit_cfg == {
            "serviceAccount": {
                "name": "fluentbit",
                "annotations": {
                    "eks.amazonaws.com/role-arn": f"arn:aws:iam::123456789012:role/k8s.{cluster_name}.fluent-bit.service"
                },
            },
            "resources": {"limits": {"cpu": "250m", "memory": "512Mi"}, "requests": {"cpu": "10m", "memory": "128Mi"}},
            "serviceMonitor": {
                "enabled": True,
                "namespace": "monitoring",
                "interval": "45s",
                "scrapeTimeout": "10s",
                "selector": {"services": "toolchain-monitoring"},
            },
            "config": {
                "inputs": "[INPUT]\n"
                "    Name              tail\n"
                "    Path              /var/log/containers/*.log\n"
                "    multiline.parser docker, cri\n"
                "    Tag               kube.*\n"
                "    Mem_Buf_Limit     15MB\n"
                "    Skip_Long_Lines   On\n",
                "filters": "[FILTER]\n"
                "    Name                kubernetes\n"
                "    Match               kube.*\n"
                "    Merge_Log           On\n"
                "    Merge_Log_Key       logJson\n"
                "    K8S-Logging.Exclude On\n",
                "outputs": "[OUTPUT]\n"
                "    Name  opensearch\n"
                f"    Host  {es_host}\n"
                "    Port  443\n"
                "    Logstash_Format On\n"
                "    Suppress_Type_Name On\n"
                "    Time_Key @timestamp\n"
                "    Replace_Dots On\n"
                f"    Logstash_Prefix  {log_name}\n"
                "    tls On\n"
                "    AWS_Auth On\n"
                f"    AWS_Region  {self._FAKE_REGION}",
            },
        }

    @mock_es_client(ES_DOMAINS)
    def test_prod_cluster(self) -> None:
        self._create_secret()
        chart = HelmChart.for_path(Path("prod/helm/observability/logging"))
        installer = self._create_installer(KubernetesCluster.PROD)
        versions = ComponentsVersions(logs_curator="latex")
        logging_values = installer._get_logging_values("puddy", chart, versions)
        self._assert_fluent_bit_cfg(logging_values.pop("fluent-bit"), "prod-logs", "yada-yada")
        assert logging_values == {
            "aws_region": "us-east-1",
            "curator": {
                "enabled": True,
                "iam_role_arn": "arn:aws:iam::123456789012:role/k8s.yada-yada.es-logging-curator.job",
                "push_gateway_url": "http://prod-monitoring-prometheus-pushgateway.monitoring.svc.cluster.local:9091",
                "image": "latex",
                "max_age": 60,
            },
            "logging_opensearch_host": "the-baby",
            "toolchain_env": "toolchain_prod",
        }

    @mock_es_client(ES_DOMAINS)
    def test_remoting_prod_cluster(self):
        self._create_secret()
        chart = HelmChart.for_path(Path("prod/helm/observability/logging"))
        installer = self._create_installer(KubernetesCluster.REMOTING)
        versions = ComponentsVersions(logs_curator="pole")
        logging_values = installer._get_logging_values("tinsel", chart, versions)
        self._assert_fluent_bit_cfg(logging_values.pop("fluent-bit"), "remoting-prod-logs", "festivus")
        assert logging_values == {
            "aws_region": "us-east-1",
            "curator": {"enabled": False},
            "logging_opensearch_host": "the-baby",
            "toolchain_env": "toolchain_prod",
        }
