#!/usr/bin/env ./python
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass
from pathlib import Path

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.kubernetes.constants import KubernetesCluster
from toolchain.prod.tools.changes_helper import ChangeHelper
from toolchain.prod.tools.deploy_notifications import notify_devops_chart_deploy
from toolchain.prod.tools.deployment_lock import DeploymentLock
from toolchain.prod.tools.utils import Deployer, IngressType, get_ingress_security_group_id, get_monitoring_secret
from toolchain.util.prod.helm_charts import HelmChart
from toolchain.util.prod.helm_client import HelmClient, HelmExecuteResult
from toolchain.util.prod.pagerduty import ToolchainPagerDutyClient

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MonitoringConfig:
    enable_prod_resources: bool
    prometheus_ingress: bool
    prometheus_adapter: bool
    remoting_rules: bool


class InstallMonitoringProd(ToolchainBinary):
    description = "Install monitoring chart to our production Kubernetes cluster."

    _NAMESPACE = "monitoring"
    LOCAL_CHART_PATH = Path("prod/helm/observability/monitoring/monitoring")
    _RELEASE_NAME = "prod-monitoring"
    _DEAD_MAN_SNITCH_RECEIVER = "dead-mans-snitch"
    _INSTALL_TIMEOUT_SEC = 600
    _EMOJI = "prometheus"
    LOCK_NAME = "monitoring"
    _PAGERDUTY_SERVICE = "toolchain_prod"
    _PAGERDUTY_INTEGRATION = "prometheus-alert-mgr"
    _EMAIL_IAM_USER = "prod-monitoring-email-user"

    _CLUSTER_CONFIG: dict[KubernetesCluster, MonitoringConfig] = {
        HelmClient.Cluster.REMOTING: MonitoringConfig(
            enable_prod_resources=False,
            prometheus_ingress=True,
            prometheus_adapter=False,
            remoting_rules=True,
        ),
        HelmClient.Cluster.PROD: MonitoringConfig(
            enable_prod_resources=True,
            prometheus_ingress=False,
            prometheus_adapter=True,
            remoting_rules=False,
        ),
    }

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        _logger.info(f"args: {cmd_args}")
        self._aws_region = cmd_args.aws_region
        self._deployer = Deployer.get_current()
        self._cluster = HelmClient.Cluster(cmd_args.cluster)
        if self._cluster not in self._CLUSTER_CONFIG:
            raise ToolchainAssertion(f"Cluster {self._cluster.value} is not known to this tool.")

        self._cluster_config = self._CLUSTER_CONFIG[self._cluster]
        self._helm = HelmClient(
            aws_region=cmd_args.aws_region,
            cluster=self._cluster,
            dry_run=cmd_args.dry_run,
            keep_helm_files=cmd_args.keep_helm_files,
        )
        self._dry_run = cmd_args.dry_run
        self._silent = cmd_args.silent
        self._helm.check_cluster_connectivity()

    def _update_chart_features(self, chart_values: dict) -> None:
        chart_values["features"].update(
            cloudwatchExporter=self._cluster_config.enable_prod_resources,
            monitorToolchainPythonServices=self._cluster_config.enable_prod_resources,
            pushGateway=True,
            remotingRules=self._cluster_config.remoting_rules,
            prometheusAdapter=self._cluster_config.prometheus_adapter,
        )

    def _update_alertmanager_values(self, chart_values: dict, prod_secrets: dict) -> None:
        alert_mgr_cfg = chart_values["kube-prometheus-stack"]["alertmanager"]["config"]
        dead_man_snitch_receiver = None
        for receiver in alert_mgr_cfg["receivers"]:
            if receiver["name"] == self._DEAD_MAN_SNITCH_RECEIVER:
                dead_man_snitch_receiver = receiver["webhook_configs"][0]
                break
        if not dead_man_snitch_receiver:
            raise ToolchainAssertion(f"Can't find Dead Man Snitch receiver({self._DEAD_MAN_SNITCH_RECEIVER})")

        deadmansnitch_webhook = prod_secrets["deadmanssnitch"]
        dead_man_snitch_receiver["url"] = deadmansnitch_webhook

        slack_webhook = prod_secrets["slack-webhook"]
        sendgrid_api_key = prod_secrets["sendgrid_api_key"]
        pd_client = ToolchainPagerDutyClient(prod_secrets["pagerduty_api_token"])
        pd_integration = pd_client.get_integration_details(
            service_name=self._PAGERDUTY_SERVICE, integration_name=self._PAGERDUTY_INTEGRATION
        )

        global_cfg = alert_mgr_cfg["global"]
        pd_config = self._get_pagerduty_cfg(alert_mgr_cfg)
        pd_config["routing_key"] = pd_integration.key
        global_cfg.update(
            slack_api_url=slack_webhook,
            pagerduty_url=pd_integration.url,
            smtp_auth_password=sendgrid_api_key,
        )

    def _get_pagerduty_cfg(self, alert_mgr_cfg: dict) -> dict:
        for receiver in alert_mgr_cfg["receivers"]:
            if "pagerduty_configs" in receiver:
                return receiver["pagerduty_configs"][0]
        raise ToolchainAssertion("Can't find PagerDuty receiver config.")

    def _update_prometheus_ingress_values(self, chart_values: dict, cluster: KubernetesCluster) -> None:
        ingress_cfg = chart_values["kube-prometheus-stack"]["prometheus"]["ingress"]
        enabled = self._cluster_config.prometheus_ingress
        ingress_cfg["enabled"] = enabled
        if not enabled:
            del ingress_cfg["annotations"]
            del ingress_cfg["hosts"]
            del ingress_cfg["paths"]
            del ingress_cfg["pathType"]
            return
        security_group_id = get_ingress_security_group_id(self._aws_region, cluster, IngressType.PEER)
        ingress_cfg["annotations"]["alb.ingress.kubernetes.io/security-groups"] = security_group_id
        ingress_cfg["hosts"].append(f"prometheus.{cluster.value}.toolchain.private")
        if len(ingress_cfg["hosts"]) != 1:
            raise ToolchainAssertion("Unexpected prometheus ingress hosts.")

    def _get_monitoring_values(self, chart: HelmChart) -> dict:
        cluster = self._helm.cluster
        chart_values = chart.get_values()
        self._update_chart_features(chart_values)
        prod_secrets = get_monitoring_secret(self._aws_region)
        chart_values["global"]["region"] = self._aws_region

        self._update_alertmanager_values(chart_values, prod_secrets)
        self._update_prometheus_ingress_values(chart_values=chart_values, cluster=cluster)

        prometheus_spec = chart_values["kube-prometheus-stack"]["prometheus"]["prometheusSpec"]
        prometheus_spec["externalLabels"]["cluster"] = cluster.value
        return chart_values

    def run(self) -> int:
        if not ChangeHelper.check_git_state():
            return -1
        chart = HelmChart.for_path(self.LOCAL_CHART_PATH)
        self._helm.update_dependencies(chart.path)
        with DeploymentLock.for_deploy(self.LOCK_NAME, self._deployer):
            exec_result, deploy_time = self._install_monitoring(chart)
        notify_devops_chart_deploy(
            chart=chart,
            exec_result=exec_result,
            deployer=self._deployer,
            deploy_time=deploy_time,
            aws_region=self._aws_region,
            emoji=self._EMOJI,
            silent=self._silent,
        )
        return 0

    def _install_monitoring(self, chart: HelmChart) -> tuple[HelmExecuteResult, datetime.datetime]:
        values = self._get_monitoring_values(chart)
        self._helm.check(chart_path=chart.path, values=values)
        self._helm.maybe_publish_chart(chart_path=chart.path, chart_name=chart.name)
        deploy_time = utcnow()
        _logger.info(
            f"Installing monitoring chart v{chart.version} on cluster {self._cluster.value}. dry_run={self._dry_run}"
        )
        exec_result = self._helm.upgrade_install_from_repo(
            release_name=self._RELEASE_NAME,
            namespace=self._NAMESPACE,
            chart=chart,
            values=values,
            install_timeout_sec=self._INSTALL_TIMEOUT_SEC,
        )
        return exec_result, deploy_time

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)
        parser.add_argument(
            "--cluster", action="store", required=True, help="Cluster into which to install monitoring stack"
        )
        parser.add_argument("--dry-run", action="store_true", required=False, default=False, help="Dry run.")
        parser.add_argument(
            "--silent", action="store_true", required=False, default=False, help="Notify alerts chat room."
        )
        parser.add_argument(
            "--keep-helm-files",
            required=False,
            action="store_true",
            default=False,
            help="Do not erase temporary files passed to helm",
        )


if __name__ == "__main__":
    InstallMonitoringProd.start()
