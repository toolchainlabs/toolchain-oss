# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from pathlib import Path

import pytest
from moto import mock_acm, mock_ec2, mock_secretsmanager

from toolchain.aws.test_utils.secrets import create_fake_secret
from toolchain.prod.installs.install_monitoring_prod import InstallMonitoringProd, MonitoringConfig
from toolchain.prod.installs.tests_helpers import FakeKubernetesCluster
from toolchain.util.prod.helm_charts import HelmChart
from toolchain.util.prod.pagerduty_test import add_service_response
from toolchain.util.test.aws.utils import create_fake_security_group


class TestInstallMonitoringProd:
    _FAKE_REGION = "ap-northeast-1"
    _CLUSTER = "yada-yada"

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_acm(), mock_ec2(), mock_secretsmanager():
            yield

    @pytest.fixture()
    def chart(self) -> HelmChart:
        return HelmChart.for_path(Path("prod/helm/observability/monitoring/monitoring"))

    def _create_installer(
        self, cluster_name: str = _CLUSTER, config: MonitoringConfig | None = None
    ) -> InstallMonitoringProd:
        fake_cluster = FakeKubernetesCluster(cluster_name)
        if config is None:
            config = MonitoringConfig(
                enable_prod_resources=True,
                prometheus_ingress=False,
                prometheus_adapter=True,
                remoting_rules=False,
            )
        InstallMonitoringProd._CLUSTER_CONFIG[fake_cluster] = config  # type: ignore[index]

        installer = InstallMonitoringProd.create_for_args(
            aws_region=self._FAKE_REGION, cluster=cluster_name, dry_run=True
        )
        # Sanity checks.
        assert installer._helm._HELM_EXECUTABLE == "no-op"
        assert installer._helm.cluster_name == cluster_name
        return installer

    def _create_secret(self) -> None:
        create_fake_secret(
            region=self._FAKE_REGION,
            name="prod/monitoring",
            secret={
                "deadmanssnitch": "https://death-certificate.george.dev",
                "grafana_google_client_id": "this pretzel is",
                "grafana_google_client_secret": "making me thirsty",
                "slack-webhook": "https://fake.chat.puffy.local",
                "sendgrid_api_key": "himalayan-walking-shoes",
                "pagerduty_api_token": "lloyd-braun",
            },
        )

    def test_fail_on_nonexistent_cluster(self) -> None:
        with pytest.raises(ValueError, match=r"is not a valid FakeKubernetesCluster"):
            self._create_installer(cluster_name="not-test-cluster")

    def test_monitoring_values(self, responses, chart: HelmChart) -> None:
        self._create_secret()
        add_service_response(responses, "toolchain_prod", "prometheus-alert-mgr")
        installer = self._create_installer()
        monitoring_values = installer._get_monitoring_values(chart)
        assert set(monitoring_values) == {
            "features",
            "kube-prometheus-stack",
            "global",
            "prometheus-cloudwatch-exporter",
            "prometheus-pushgateway",
            "prometheus-adapter",
        }
        assert monitoring_values["features"] == {
            "cloudwatchExporter": True,
            "monitorToolchainPythonServices": True,
            "pushGateway": True,
            "prometheusAdapter": True,
            "remotingRules": False,
        }
        assert monitoring_values["global"] == {"region": "ap-northeast-1"}
        operator_values = monitoring_values["kube-prometheus-stack"]
        assert set(operator_values) == {
            "fullnameOverride",
            "nameOverride",
            "commonLabels",
            "kubeControllerManager",
            "kubeScheduler",
            "prometheusOperator",
            "grafana",
            "kubeEtcd",
            "alertmanager",
            "kube-state-metrics",
            "kubelet",
            "defaultRules",
            "prometheus",
            "prometheus-node-exporter",
            "prometheusConfigReloader",
        }
        assert operator_values["commonLabels"] == {"services": "toolchain-monitoring"}
        prometheus_spec = operator_values["prometheus"]["prometheusSpec"]
        assert prometheus_spec == {
            "externalLabels": {"cluster": "yada-yada"},
            "serviceMonitorSelector": {"matchLabels": {"services": "toolchain-monitoring"}},
            "logFormat": "json",
            "retentionSize": "150GiB",
            "retention": "16w",
            "resources": {
                "limits": {"cpu": "2000m", "memory": "8Gi"},
                "requests": {"cpu": "300m", "memory": "1024Mi"},
            },
            "storageSpec": {
                "volumeClaimTemplate": {
                    "spec": {"resources": {"requests": {"storage": "200Gi"}}, "storageClassName": "gp2"}
                }
            },
        }
        alert_mgr = operator_values["alertmanager"]["config"]
        assert alert_mgr["global"] == {
            "pagerduty_url": "https://events.pagerduty.com/v2/enqueue",
            "slack_api_url": "https://fake.chat.puffy.local",
            "smtp_auth_password": "himalayan-walking-shoes",
            "smtp_auth_username": "apikey",
            "smtp_require_tls": True,
            "smtp_smarthost": "smtp.sendgrid.net:587",
        }
        receivers_dict = {receiver["name"]: receiver for receiver in alert_mgr["receivers"]}
        assert len(receivers_dict) == 6
        assert receivers_dict["pagerduty"] == {
            "name": "pagerduty",
            "pagerduty_configs": [{"routing_key": "SOUP", "send_resolved": True}],
        }
        assert receivers_dict["dead-mans-snitch"] == {
            "name": "dead-mans-snitch",
            "webhook_configs": [{"send_resolved": True, "url": "https://death-certificate.george.dev"}],
        }
        assert operator_values["grafana"] == {"enabled": False}
        prometheus_ingress_cfg = operator_values["prometheus"]["ingress"]
        assert prometheus_ingress_cfg == {"enabled": False}
        assert operator_values["prometheus"]["service"] == {"port": 80}

    def test_monitoring_values_for_remoting(self, responses, chart: HelmChart) -> None:
        self._create_secret()
        add_service_response(responses, "toolchain_prod", "prometheus-alert-mgr")
        security_group_id = create_fake_security_group(region=self._FAKE_REGION, group_name="k8s.yada-yada.vpc-ingress")
        installer = self._create_installer(
            config=MonitoringConfig(
                enable_prod_resources=False,
                prometheus_ingress=True,
                prometheus_adapter=False,
                remoting_rules=True,
            )
        )
        monitoring_values = installer._get_monitoring_values(chart)
        assert set(monitoring_values) == {
            "features",
            "kube-prometheus-stack",
            "global",
            "prometheus-cloudwatch-exporter",
            "prometheus-pushgateway",
            "prometheus-adapter",
        }
        assert not monitoring_values["features"]["cloudwatchExporter"]
        assert not monitoring_values["features"]["monitorToolchainPythonServices"]
        assert monitoring_values["features"]["remotingRules"]
        assert not monitoring_values["kube-prometheus-stack"]["grafana"]["enabled"]
        assert "ingress" not in monitoring_values

        operator_values = monitoring_values["kube-prometheus-stack"]

        assert set(operator_values) == {
            "fullnameOverride",
            "nameOverride",
            "commonLabels",
            "kubeControllerManager",
            "kubeScheduler",
            "prometheusOperator",
            "grafana",
            "kubeEtcd",
            "alertmanager",
            "defaultRules",
            "kubelet",
            "kube-state-metrics",
            "prometheus",
            "prometheus-node-exporter",
            "prometheusConfigReloader",
        }
        assert operator_values["commonLabels"] == {"services": "toolchain-monitoring"}
        assert operator_values["grafana"] == {"enabled": False}
        alert_mgr = operator_values["alertmanager"]["config"]
        assert alert_mgr["global"] == {
            "pagerduty_url": "https://events.pagerduty.com/v2/enqueue",
            "slack_api_url": "https://fake.chat.puffy.local",
            "smtp_auth_password": "himalayan-walking-shoes",
            "smtp_auth_username": "apikey",
            "smtp_require_tls": True,
            "smtp_smarthost": "smtp.sendgrid.net:587",
        }
        receivers_dict = {receiver["name"]: receiver for receiver in alert_mgr["receivers"]}
        assert len(receivers_dict) == 6
        assert receivers_dict["pagerduty"] == {
            "name": "pagerduty",
            "pagerduty_configs": [{"routing_key": "SOUP", "send_resolved": True}],
        }
        assert receivers_dict["dead-mans-snitch"] == {
            "name": "dead-mans-snitch",
            "webhook_configs": [{"send_resolved": True, "url": "https://death-certificate.george.dev"}],
        }
        prometheus_ingress_cfg = operator_values["prometheus"]["ingress"]
        assert prometheus_ingress_cfg == {
            "enabled": True,
            "hosts": ["prometheus.yada-yada.toolchain.private"],
            "paths": ["/*"],
            "pathType": "ImplementationSpecific",
            "annotations": {
                "kubernetes.io/ingress.class": "alb",
                "alb.ingress.kubernetes.io/scheme": "internal",
                "alb.ingress.kubernetes.io/listen-ports": '[{"HTTP": 80}]',
                "alb.ingress.kubernetes.io/security-groups": security_group_id,
                "alb.ingress.kubernetes.io/target-type": "ip",
                "alb.ingress.kubernetes.io/backend-protocol": "HTTP",
                "alb.ingress.kubernetes.io/healthcheck-protocol": "HTTP",
                "alb.ingress.kubernetes.io/healthcheck-port": "traffic-port",
                "alb.ingress.kubernetes.io/healthcheck-path": "/-/healthy",
                "alb.ingress.kubernetes.io/healthcheck-interval-seconds": "15",
                "alb.ingress.kubernetes.io/healthcheck-timeout-seconds": "5",
                "alb.ingress.kubernetes.io/success-codes": "200",
                "alb.ingress.kubernetes.io/healthy-threshold-count": "2",
                "alb.ingress.kubernetes.io/unhealthy-threshold-count": "2",
                "alb.ingress.kubernetes.io/ip-address-type": "ipv4",
                "alb.ingress.kubernetes.io/load-balancer-attributes": "access_logs.s3.enabled=true,access_logs.s3.bucket=logs.us-east-1.toolchain.com,access_logs.s3.prefix=elb-access-logs/remoting",
            },
        }
