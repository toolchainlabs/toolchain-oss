#!/usr/bin/env ./python
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
from argparse import ArgumentParser, Namespace
from pathlib import Path

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.kubernetes.constants import KubernetesCluster
from toolchain.prod.tools.deploy_notifications import notify_devops_chart_deploy
from toolchain.prod.tools.deployment_lock import DeploymentLock
from toolchain.prod.tools.utils import Deployer, set_service_account_annotations
from toolchain.util.prod.helm_charts import HelmChart
from toolchain.util.prod.helm_client import HelmClient

_logger = logging.getLogger(__name__)


class ExternalDNSChartInstaller(ToolchainBinary):
    LOCAL_CHART_PATH = Path("prod/helm/aws/external-dns/")
    _RELEASE = "external-dns"
    _EMOJI = "dns"
    _PROD_CLUSTER_ONLY_DOMAINS = ("toolchainlabs.com", "graphmycode.com", "graphmyrepo.com")

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._aws_region = cmd_args.aws_region
        self._dry_run = cmd_args.dry_run
        self._deployer = Deployer.get_current()
        self._helm = HelmClient(
            aws_region=cmd_args.aws_region, cluster=KubernetesCluster(cmd_args.cluster), dry_run=cmd_args.dry_run
        )
        self._namespace = "kube-system"
        self._helm.check_cluster_connectivity()

    def _get_values(self, chart: HelmChart) -> dict:
        values = chart.get_values()
        cluster_name = self._helm.cluster_name
        external_dns_config = values["external-dns"]
        set_service_account_annotations(
            external_dns_config, aws_region=self._aws_region, cluster=self._helm.cluster, service="external-dns"
        )
        external_dns_config["txtOwnerId"] = cluster_name
        if self._helm.cluster == KubernetesCluster.PROD:
            external_dns_config["domainFilters"].extend(self._PROD_CLUSTER_ONLY_DOMAINS)

        return values

    def run(self) -> int:
        chart = HelmChart.for_path(self.LOCAL_CHART_PATH)
        self._helm.update_dependencies(chart.path)
        values = self._get_values(chart)
        self._helm.check(chart_path=chart.path, values=values)
        deploy_time = utcnow()
        with DeploymentLock.for_deploy("external-dns", self._deployer):
            self._helm.maybe_publish_chart(chart.path, chart.name)
            exec_result = self._helm.upgrade_install_from_repo(
                release_name=self._RELEASE, namespace=self._namespace, chart=chart, values=values
            )
        notify_devops_chart_deploy(
            chart=chart,
            exec_result=exec_result,
            deployer=self._deployer,
            deploy_time=deploy_time,
            aws_region=self._aws_region,
            emoji=self._EMOJI,
        )
        return 0

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)
        parser.add_argument("--dry-run", action="store_true", required=False, default=False, help="Do a dry run.")
        parser.add_argument(
            "--cluster",
            type=str,
            action="store",
            default=HelmClient.Cluster.PROD.value,
            help="Override the cluster to operate on",
        )


if __name__ == "__main__":
    ExternalDNSChartInstaller.start()
