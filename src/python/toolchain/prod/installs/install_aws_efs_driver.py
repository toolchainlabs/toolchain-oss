#!/usr/bin/env ./python
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
from argparse import ArgumentParser, Namespace
from pathlib import Path

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.kubernetes.constants import KubernetesCluster
from toolchain.prod.tools.changes_helper import ChangeHelper
from toolchain.prod.tools.deploy_notifications import notify_devops_chart_deploy
from toolchain.prod.tools.deployment_lock import DeploymentLock
from toolchain.prod.tools.resources_resolver import DEV_EFS_FILE_SYSTEM_ID, REMOTING_PROD_EFS_FILE_SYSTEM_ID
from toolchain.prod.tools.utils import Deployer
from toolchain.util.prod.helm_charts import HelmChart
from toolchain.util.prod.helm_client import HelmClient

_logger = logging.getLogger(__name__)


class InstallAwsEFSDriver(ToolchainBinary):
    description = "Install AWS EFS CSI Driver for Kubernetes in a cluster."
    _NAMESPACE = "kube-system"
    LOCAL_CHART_PATH = Path("prod/helm/aws/aws-efs-csi-driver")
    _INSTALL_TIMEOUT_SEC = 600
    _RELEASE = "aws-efs-csi-driver"
    _EMOJI = "tbd"
    _FS_TO_CLUSTER = {
        KubernetesCluster.DEV: DEV_EFS_FILE_SYSTEM_ID,
        KubernetesCluster.REMOTING: REMOTING_PROD_EFS_FILE_SYSTEM_ID,
    }

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._aws_region = cmd_args.aws_region
        self._deployer = Deployer.get_current()
        cluster = KubernetesCluster(cmd_args.cluster)
        if cluster not in {KubernetesCluster.DEV, KubernetesCluster.REMOTING}:
            raise ToolchainAssertion("Only remoting and dev cluster are currently supported.")
        self._is_prod = cluster != KubernetesCluster.DEV
        self._helm = HelmClient(
            aws_region=cmd_args.aws_region,
            cluster=cluster,
            dry_run=False,
        )
        self._helm.check_cluster_connectivity()

    def _get_values(self, chart: HelmChart) -> dict:
        values = chart.get_values()
        values["aws"]["iam_role"] = f"k8s.{self._helm.cluster_name}.aws-efs-csi-driver"
        values["efsFileSystemId"] = self._FS_TO_CLUSTER[self._helm.cluster]
        return values

    def _install(self) -> None:
        chart = HelmChart.for_path(self.LOCAL_CHART_PATH)
        self._helm.update_dependencies(chart.path)
        values = self._get_values(chart)
        deploy_time = utcnow()
        with DeploymentLock.for_deploy("aws-efs-csi-driver", self._deployer):
            self._helm.maybe_publish_chart(chart.path, chart.name)
            exec_result = self._helm.upgrade_install_from_repo(
                release_name=self._RELEASE,
                namespace=self._NAMESPACE,
                chart=chart,
                values=values,
                install_timeout_sec=self._INSTALL_TIMEOUT_SEC,
            )
        notify_devops_chart_deploy(
            chart=chart,
            exec_result=exec_result,
            deployer=self._deployer,
            deploy_time=deploy_time,
            aws_region=self._aws_region,
            emoji=self._EMOJI,
            is_prod=self._is_prod,
        )

    def run(self) -> int:
        if self._is_prod and not ChangeHelper.check_git_state():
            return -1
        self._install()
        return 0

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)
        parser.add_argument("--cluster", required=True, help="Target cluster")


if __name__ == "__main__":
    InstallAwsEFSDriver.start()
