# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from pathlib import Path
from unittest import mock

import pytest
from moto import mock_acm, mock_ec2, mock_secretsmanager

from toolchain.aws.test_utils.secrets import create_fake_secret
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.prod.installs.install_grafana_prod import InstallGrafanaProd
from toolchain.util.prod.helm_charts import HelmChart
from toolchain.util.test.aws.utils import create_fake_cert, create_fake_security_group


class FakeKubernetesSecretsAccessor:
    @classmethod
    def create(cls, namespace: str, cluster: str):
        return cls()

    def get_json_secret_or_raise(self, secret_name) -> dict:
        return {"token": "Kitzmiller"}


@mock.patch("toolchain.prod.installs.install_grafana_prod.KubernetesSecretsAccessor", new=FakeKubernetesSecretsAccessor)
class TestInstallGrafanaProd:
    _FAKE_REGION = "ap-northeast-1"
    _CLUSTER = "yada-yada"

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_acm(), mock_ec2(), mock_secretsmanager():
            yield

    @pytest.fixture()
    def grafana_chart(self) -> HelmChart:
        return HelmChart.for_path(Path("prod/helm/observability/monitoring/grafana"))

    def _create_installer(self) -> InstallGrafanaProd:
        installer = InstallGrafanaProd.create_for_args(aws_region=self._FAKE_REGION, dry_run=True)
        # Sanity checks.
        assert installer._helm._HELM_EXECUTABLE == "no-op"
        assert installer._helm.cluster_name == "yada-yada"
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
                "iam_access_key": "darryl-nelson",
                "iam_access_secret": "himalayan-walking-shoes",
            },
        )

    def test_fail_on_missing_security_group(self, grafana_chart: HelmChart) -> None:
        self._create_secret()
        installer = self._create_installer()

        with pytest.raises(ToolchainAssertion, match="Security group 'k8s.yada-yada.vpn.ingress' not found."):
            installer._get_monitoring_values(grafana_chart.get_values())
        create_fake_security_group(region=self._FAKE_REGION, group_name="k8s.not-cluster.vpn.ingress")
        with pytest.raises(ToolchainAssertion, match="Security group 'k8s.yada-yada.vpn.ingress' not found."):
            installer._get_monitoring_values(grafana_chart.get_values())

    def test_fail_on_missing_cert(self, grafana_chart: HelmChart) -> None:
        self._create_secret()
        installer = self._create_installer()
        create_fake_security_group(region=self._FAKE_REGION, group_name="k8s.yada-yada.vpn.ingress")
        with pytest.raises(ToolchainAssertion, match="Couldn't find cert for"):
            installer._get_monitoring_values(grafana_chart.get_values())
        create_fake_cert(region=self._FAKE_REGION, fqdn="george.test.com")
        with pytest.raises(ToolchainAssertion, match="Couldn't find cert for"):
            installer._get_monitoring_values(grafana_chart.get_values())

    def test_grafana_values(self, grafana_chart: HelmChart) -> None:
        self._create_secret()
        cert_arn = create_fake_cert(region=self._FAKE_REGION, fqdn="grafana.toolchainlabs.com")
        security_group_id = create_fake_security_group(region=self._FAKE_REGION, group_name="k8s.yada-yada.vpn.ingress")
        installer = self._create_installer()
        grafana_values = installer._get_monitoring_values(grafana_chart.get_values())
        assert set(grafana_values) == {"grafana", "ingress", "global", "influxdb"}

        assert grafana_values["global"] == {"region": "ap-northeast-1"}
        ingress = grafana_values["ingress"]
        assert ingress == {
            "name": "grafana",
            "enabled": True,
            "scheme": "internal",
            "logs_prefix": "yada-yada",
            "healthcheck_path": "/api/health",
            "external_ingress_sg_id": {"ap-northeast-1": security_group_id},
            "ssl_certificate_arn": {"ap-northeast-1": cert_arn},
            "rules": [
                {
                    "host": "grafana.toolchainlabs.com",
                    "http": {
                        "paths": [
                            {
                                "path": "/",
                                "pathType": "Prefix",
                                "backend": {"service": {"name": "prod-grafana", "port": {"number": 80}}},
                            }
                        ]
                    },
                }
            ],
        }
        grafana_auth = grafana_values["grafana"]["grafana.ini"]["auth.google"]
        assert grafana_auth == {
            "enabled": True,
            "client_id": "this pretzel is",
            "client_secret": "making me thirsty",
            "scopes": "https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email",
            "auth_url": "https://accounts.google.com/o/oauth2/auth",
            "token_url": "https://accounts.google.com/o/oauth2/token",
            "allowed_domains": "toolchain.com",
            "allow_sign_up": True,
        }
        assert grafana_values["influxdb"] == {
            "url": "http://influxdb.prod.svc.cluster.local:80",
            "tokens": [
                {"token": "Kitzmiller", "org": "buildsense", "defaultBucket": "pantsbuild/pants"},
                {"token": "Kitzmiller", "org": "pants-telemetry", "defaultBucket": "anonymous-telemetry"},
            ],
        }
