#!/usr/bin/env ./python
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from argparse import ArgumentParser, Namespace
from pathlib import Path

from toolchain.aws.eks import EKS
from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.kubernetes.cluster import ClusterAPI
from toolchain.prod.tools.changes_helper import ChangeHelper
from toolchain.prod.tools.deploy_notifications import notify_devops_chart_deploy
from toolchain.prod.tools.deployment_lock import DeploymentLock
from toolchain.prod.tools.utils import Deployer, set_service_account_annotations
from toolchain.util.prod.helm_charts import HelmChart
from toolchain.util.prod.helm_client import HelmClient

_logger = logging.getLogger(__name__)


class AwsAlbIngressControllerChartInstaller(ToolchainBinary):
    LOCAL_CHART_PATH = Path("prod/helm/aws/aws-alb-ingress-controller/")
    _RELEASE = "aws-alb-ingress-controller"
    _EMOJI = "ingress"
    READINESS_GATE_LABELS = {"elbv2.k8s.aws/pod-readiness-gate-inject": "enabled"}

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._aws_region = cmd_args.aws_region
        self._dry_run = cmd_args.dry_run
        self._deployer = Deployer.get_current()
        cluster = HelmClient.Cluster(cmd_args.cluster)
        self._helm = HelmClient(aws_region=cmd_args.aws_region, cluster=cluster, dry_run=cmd_args.dry_run)
        self._namespace = "kube-system"
        self._helm.check_cluster_connectivity()

    def _get_values(self, chart: HelmChart) -> dict:
        values = chart.get_values()
        config = values["aws-load-balancer-controller"]
        cluster_name = self._helm.cluster.value
        vpc_id = EKS(self._aws_region).get_cluster_vpc_id(cluster_name)
        config.update(
            region=self._aws_region,
            vpcId=vpc_id,
            clusterName=cluster_name,
        )
        set_service_account_annotations(
            config, aws_region=self._aws_region, cluster=self._helm.cluster, service="ingress"
        )
        return values

    def _set_pod_readiness_gate_label(self, namespaces: tuple[str, ...]) -> None:
        # https://kubernetes-sigs.github.io/aws-load-balancer-controller/guide/controller/pod_readiness_gate/
        cluster_api = ClusterAPI.for_cluster(self._helm.cluster)
        for ns in namespaces:
            labels = cluster_api.set_namespace_labels(namespace=ns, labels=self.READINESS_GATE_LABELS)
            _logger.info(f"namespace={ns} {labels=}")

    def run(self) -> int:
        chart = HelmChart.for_path(self.LOCAL_CHART_PATH)
        self._helm.update_dependencies(chart.path)
        values = self._get_values(chart)
        self._helm.check(chart_path=chart.path, values=values)
        deploy_time = utcnow()
        if not ChangeHelper.check_git_state():
            return -1
        with DeploymentLock.for_deploy("aws-alb-ingress-controller", self._deployer):
            self._helm.maybe_publish_chart(chart.path, chart.name)
            exec_result = self._helm.upgrade_install_from_repo(
                release_name=self._RELEASE, namespace=self._namespace, chart=chart, values=values
            )
        self._set_pod_readiness_gate_label(namespaces=("prod", "staging", "monitoring"))
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
    AwsAlbIngressControllerChartInstaller.start()
