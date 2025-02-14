#!/usr/bin/env ./python
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from argparse import ArgumentParser, Namespace
from pathlib import Path

from toolchain.aws.acm import ACM
from toolchain.base.datetime_tools import utcnow
from toolchain.base.password import generate_password
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.prod.installs.install_influxdb import InstallAndBootstrapInfluxDB
from toolchain.prod.installs.install_monitoring_prod import InstallMonitoringProd
from toolchain.prod.tools.changes_helper import ChangeHelper
from toolchain.prod.tools.deploy_notifications import notify_devops_chart_deploy
from toolchain.prod.tools.deployment_lock import DeploymentLock
from toolchain.prod.tools.utils import Deployer, IngressType, get_ingress_security_group_id, get_monitoring_secret
from toolchain.util.prod.helm_charts import HelmChart
from toolchain.util.prod.helm_client import HelmClient, HelmExecuteResult
from toolchain.util.secret.secrets_accessor import KubernetesSecretsAccessor

_logger = logging.getLogger(__name__)


class InstallGrafanaProd(ToolchainBinary):
    description = "Temporary standalone Grafana installer"

    _NAMESPACE = "monitoring"
    LOCAL_CHART_PATH = Path("prod/helm/observability/monitoring/grafana")
    _GRAFANA_DOMAIN = "grafana.toolchainlabs.com"
    _RELEASE_NAME = "prod-grafana"

    _EMOJI = "grafana"

    _INFLUXDB_ORGS = (  # org, default-bucket
        ("buildsense", "pantsbuild/pants"),
        ("pants-telemetry", "anonymous-telemetry"),
    )

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._aws_region = cmd_args.aws_region
        self._helm = HelmClient(
            aws_region=cmd_args.aws_region, cluster=HelmClient.Cluster.PROD, dry_run=cmd_args.dry_run
        )
        self._dry_run = cmd_args.dry_run
        self._deployer = Deployer.get_current()
        self._helm.check_cluster_connectivity()

    def _get_monitoring_values(self, chart_values: dict) -> dict:
        aws_region = self._aws_region
        prod_secrets = get_monitoring_secret(aws_region)

        influxdb_tokens = self._get_influx_db_tokens()
        ingress_cfg = chart_values["ingress"]
        grafana_cfg = chart_values["grafana"]
        chart_values["global"]["region"] = self._aws_region
        google_client_id = prod_secrets["grafana_google_client_id"]
        google_client_secret = prod_secrets["grafana_google_client_secret"]
        google_auth = grafana_cfg["grafana.ini"]["auth.google"]
        google_auth.update(client_id=google_client_id, client_secret=google_client_secret)
        grafana_cfg["adminPassword"] = generate_password(length=20)
        security_group_id = get_ingress_security_group_id(aws_region, self._helm.cluster, IngressType.PRIVATE)
        cert_arn = ACM(aws_region).get_cert_arn_for_domain(self._GRAFANA_DOMAIN)
        if not cert_arn:
            raise ToolchainAssertion(f"Couldn't find cert for {self._GRAFANA_DOMAIN}")
        influxdb_tokens_cfg = chart_values["influxdb"]["tokens"]
        influxdb_tokens_cfg.extend(influxdb_tokens)
        ingress_cfg.update(
            ssl_certificate_arn={aws_region: cert_arn},
            external_ingress_sg_id={aws_region: security_group_id},
            logs_prefix=self._helm.cluster_name,
            enabled=True,
        )
        return chart_values

    def _get_influx_db_tokens(self) -> list[dict[str, str]]:
        accessor = KubernetesSecretsAccessor.create(namespace="prod", cluster=self._helm.cluster)
        tokens: list[dict[str, str]] = []
        for org, bucket in self._INFLUXDB_ORGS:
            influxdb_secret_name = InstallAndBootstrapInfluxDB.get_external_ro_user_secret_name(service=org)
            influxdb_user = accessor.get_json_secret_or_raise(influxdb_secret_name)
            tokens.append({"org": org, "token": influxdb_user["token"], "defaultBucket": bucket})
        return tokens

    def run(self) -> int:
        chart = HelmChart.for_path(self.LOCAL_CHART_PATH)
        self._helm.update_dependencies(chart.path)
        deploy_time = utcnow()
        if not ChangeHelper.check_git_state():
            return -1
        with DeploymentLock.for_deploy(InstallMonitoringProd.LOCK_NAME, self._deployer):
            exec_result = self._install_grafana(chart)
        notify_devops_chart_deploy(
            chart=chart,
            exec_result=exec_result,
            deployer=self._deployer,
            deploy_time=deploy_time,
            aws_region=self._aws_region,
            emoji=self._EMOJI,
        )
        return 0

    def _install_grafana(self, chart: HelmChart) -> HelmExecuteResult:
        values = self._get_monitoring_values(chart.get_values())
        self._helm.check(chart_path=chart.path, values=values)
        self._helm.maybe_publish_chart(chart_path=chart.path, chart_name=chart.name)
        _logger.info(
            f"Installing grafana-monitoring chart v{chart.version} on cluster {self._helm.cluster_name}. dry_run={self._dry_run}"
        )
        return self._helm.upgrade_install_from_repo(
            release_name=self._RELEASE_NAME, namespace=self._NAMESPACE, chart=chart, values=values
        )

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)
        parser.add_argument("--dry-run", action="store_true", required=False, default=False, help="Dry run.")


if __name__ == "__main__":
    InstallGrafanaProd.start()
