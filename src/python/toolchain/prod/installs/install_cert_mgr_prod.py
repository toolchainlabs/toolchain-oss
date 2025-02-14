#!/usr/bin/env ./python
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
from argparse import ArgumentParser, Namespace
from pathlib import Path

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.prod.tools.deploy_notifications import notify_devops_chart_deploy
from toolchain.prod.tools.deployment_lock import DeploymentLock
from toolchain.prod.tools.utils import Deployer
from toolchain.util.prod.helm_charts import HelmChart
from toolchain.util.prod.helm_client import HelmClient, HelmExecuteResult

_logger = logging.getLogger(__name__)


class InstallCertManagerProd(ToolchainBinary):
    description = "Install Cert Manager chart to a Kubernetes cluster."

    _NAMESPACE = "cert-manager"
    _LOCAL_CHART_PATH = Path("prod/helm/tools/cert-manager")
    _RELEASE_NAME = "cert-manager"
    _EMOJI = "cert-mgr"
    LOCK_NAME = "cert-manager"

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._aws_region = cmd_args.aws_region
        self._deployer = Deployer.get_current()
        self._cluster = cmd_args.cluster
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
        chart = HelmChart.for_path(self._LOCAL_CHART_PATH)
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

    def _install(self, chart: HelmChart) -> tuple[HelmExecuteResult, datetime.datetime]:
        values = chart.get_values()
        self._helm.check(chart_path=chart.path, values=values)
        self._helm.maybe_publish_chart(chart_path=chart.path, chart_name=chart.name)
        deploy_time = utcnow()
        _logger.info(
            f"Installing cert-manager chart v{chart.version} on cluster {self._cluster}. dry_run={self._dry_run}"
        )
        exec_result = self._helm.upgrade_install_from_repo(
            release_name=self._RELEASE_NAME, namespace=self._NAMESPACE, chart=chart, values=values
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
            help="Cluster into which to install cert-manager",
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
    InstallCertManagerProd.start()
