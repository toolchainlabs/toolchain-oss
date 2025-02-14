#!/usr/bin/env ./python
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from argparse import ArgumentParser, Namespace
from datetime import datetime
from pathlib import Path

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.prod.tools.deploy_notifications import notify_devops_chart_deploy
from toolchain.prod.tools.deployment_lock import DeploymentLock
from toolchain.prod.tools.utils import Deployer
from toolchain.util.prod.helm_charts import HelmChart
from toolchain.util.prod.helm_client import HelmClient, HelmExecuteResult

_logger = logging.getLogger(__name__)


class InstallRemotingRedis(ToolchainBinary):
    description = "Install Buildfarm Redis to production cluster."
    _LOCAL_CHART_PATH = Path("prod/helm/remoting/buildfarm-cas-dev")
    _NAMESPACE = "prod"
    _RELEASE_NAME = "buildfarm-redis"
    _EMOJI = "rocket"

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._aws_region = cmd_args.aws_region
        self._deployer = Deployer.get_current()
        self._silent = cmd_args.silent
        self._helm = HelmClient(
            aws_region=cmd_args.aws_region, cluster=HelmClient.Cluster.REMOTING, dry_run=cmd_args.dry_run
        )
        self._dry_run = cmd_args.dry_run
        self._helm.check_cluster_connectivity()

    def _publish_and_install(self, chart: HelmChart, values: dict) -> tuple[HelmExecuteResult, datetime]:
        deploy_time = utcnow()
        self._helm.check(chart_path=chart.path, values=values)
        self._helm.maybe_publish_chart(chart_path=chart.path, chart_name=chart.name)
        _logger.info(f"Installing buildfarm-cas-dev chart v{chart.version} on prod cluster. dry_run={self._dry_run}")
        exec_result = self._helm.upgrade_install_from_repo(
            release_name=self._RELEASE_NAME, namespace=self._NAMESPACE, chart=chart, values=values
        )
        return exec_result, deploy_time

    def run(self) -> int:
        chart = HelmChart.for_path(self._LOCAL_CHART_PATH)
        values = chart.get_values()
        values["redis-cluster"].update(nodeSelector={"toolchain.instance_category": "worker"})

        self._helm.update_dependencies(chart.path)
        with DeploymentLock.for_deploy("buildfarm-redis", self._deployer):
            exec_result, deploy_time = self._publish_and_install(chart, values=values)
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

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)
        parser.add_argument("--dry-run", action="store_true", required=False, default=False, help="Dry run.")
        parser.add_argument("--silent", action="store_true", required=False, default=False, help="Silent mode.")


if __name__ == "__main__":
    InstallRemotingRedis.start()
