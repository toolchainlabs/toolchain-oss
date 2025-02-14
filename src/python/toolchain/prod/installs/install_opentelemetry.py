#!/usr/bin/env ./python
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
from argparse import ArgumentParser, Namespace
from pathlib import Path

from toolchain.aws.secretsmanager import SecretsManager
from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.kubernetes.constants import KubernetesCluster
from toolchain.prod.tools.deploy_notifications import notify_devops_chart_deploy
from toolchain.prod.tools.deployment_lock import DeploymentLock
from toolchain.prod.tools.utils import Deployer
from toolchain.util.prod.helm_charts import HelmChart
from toolchain.util.prod.helm_client import HelmClient, HelmExecuteResult

_logger = logging.getLogger(__name__)


class InstallOpenTelemetry(ToolchainBinary):
    description = "Install opentelemetry chart to a Kubernetes cluster."

    _NAMESPACE = "opentelemetry"
    LOCAL_CHART_PATH = Path("prod/helm/observability/tracing/opentelemetry")
    _RELEASE_NAME = "opentelemetry"
    _INSTALL_TIMEOUT_SEC = 600
    _EMOJI = "trackball"
    LOCK_NAME = "opentelemetry"

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        _logger.info(f"InstallOpenTelemetry arguments: {cmd_args}")
        self._aws_region = cmd_args.aws_region
        self._deployer = Deployer.get_current()
        self._cluster = KubernetesCluster(cmd_args.cluster)
        self._helm = HelmClient(
            aws_region=cmd_args.aws_region,
            cluster=self._cluster,
            dry_run=cmd_args.dry_run,
            keep_helm_files=cmd_args.keep_helm_files,
        )
        self._dry_run = cmd_args.dry_run
        self._silent = cmd_args.silent
        self._helm.check_cluster_connectivity()

    def run(self) -> int:
        chart = HelmChart.for_path(self.LOCAL_CHART_PATH)
        self._helm.update_dependencies(chart.path)
        with DeploymentLock.for_deploy(self.LOCK_NAME, self._deployer):
            exec_result, deploy_time = self._install(chart)
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

    def _get_honeycomb_api_key(self, cluster: KubernetesCluster) -> str:
        """Load the Honeycomb API Key from AWS Secrets Manager."""
        # TODO: we should use ensure_secret to install the secret and not put it in the chart values, since it is not very secure to do so.
        secrets_mgr = SecretsManager(region=self._aws_region)
        secret_name = "honeycomb/api-key/dev" if cluster.is_dev_cluster else "honeycomb/api-key/prod"
        secret_value = secrets_mgr.get_secret(secret_name)
        if not secret_value:
            raise ValueError(f"Secret value for {secret_name} does not exist.")
        return secret_value

    def _update_values(self, values: dict, cluster: KubernetesCluster) -> None:
        values["honeycomb"].update(
            apiKey=self._get_honeycomb_api_key(cluster),
            dataset="dev-traces" if self._cluster.is_dev_cluster else "traces",
        )

    def _install(self, chart: HelmChart) -> tuple[HelmExecuteResult, datetime.datetime]:
        values = chart.get_values()
        self._update_values(values, self._cluster)
        self._helm.check(chart_path=chart.path, values=values)
        self._helm.maybe_publish_chart(chart_path=chart.path, chart_name=chart.name)
        deploy_time = utcnow()
        _logger.info(
            f"Installing opentelemetry chart v{chart.version} on cluster {self._cluster.value}. dry_run={self._dry_run}"
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
            "--cluster",
            action="store",
            required=False,
            default=HelmClient.Cluster.REMOTING.value,
            help="Cluster into which to install open telemetrys",
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
    InstallOpenTelemetry.start()
