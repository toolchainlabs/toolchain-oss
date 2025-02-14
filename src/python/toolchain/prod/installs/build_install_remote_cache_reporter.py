#!/usr/bin/env ./python
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from argparse import ArgumentParser, Namespace
from pathlib import Path

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.kubernetes.constants import KubernetesCluster, KubernetesProdNamespaces
from toolchain.prod.builders.build_pex_wrapper import PexWrapperBuilder
from toolchain.prod.tools.changes_helper import ChangeHelper
from toolchain.prod.tools.deploy_notifications import notify_devops_chart_deploy
from toolchain.prod.tools.deployment_lock import DeploymentLock
from toolchain.prod.tools.resources_resolver import CUSTOMER_EXPORT_S3_URL_PROD, get_efs_ids
from toolchain.prod.tools.utils import Deployer, get_slack_webhook_url
from toolchain.util.net.net_util import get_remote_username
from toolchain.util.prod.helm_charts import HelmChart
from toolchain.util.prod.helm_client import HelmClient

_logger = logging.getLogger(__name__)


class BuildAndDeployCacheUsageReporter(ToolchainBinary):
    _NAME = "remote-cache-usage-reporter"
    _PEX_TARGET = "src/python/toolchain/remoting:remote_cache_usage_reporter"
    _CHART_PATH = Path("prod/helm/devops/remote-cache-usage-reporter/")
    _BUCKET = "artifacts.us-east-1.toolchain.com"
    _EMOJI = "evillightsaber"

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._aws_region = cmd_args.aws_region
        self._is_prod = cmd_args.prod
        if cmd_args.prod:
            self._namespace = KubernetesProdNamespaces.PROD
            cluster = KubernetesCluster.REMOTING
        else:
            cluster = KubernetesCluster.DEV
            self._namespace = cmd_args.namespace or get_remote_username()
        self._helm = HelmClient(aws_region=cmd_args.aws_region, cluster=cluster)
        self._deployer = Deployer.get_current()
        self._helm.check_cluster_connectivity()

    def _build_and_push_image(self) -> str:
        builder = PexWrapperBuilder(pants_target=self._PEX_TARGET)
        return builder.build_and_publish()

    def _get_chart_values(self, image_tag: str) -> dict:
        redis_cluster_prefix = "remoting-prod-sharded-shard-" if self._is_prod else "dev-test-shard-"
        chart_values = HelmChart.get_chart_values(self._CHART_PATH)
        s3_path_part = "prod/remote-cache" if self._is_prod else f"dev/remote-cache/{self._namespace}"
        slack_webhook = get_slack_webhook_url(self._aws_region) if self._is_prod else None
        chart_values.update(
            image=image_tag,
            iam_role=f"k8s.{self._helm.cluster_name}.remote-cache-usage-reporter.job",
            redis_cluster_prefix=redis_cluster_prefix,
            s3_base_path=f"s3://{self._BUCKET}/{s3_path_part}",
            slack_webhook=slack_webhook,
            customers_map_s3_url=CUSTOMER_EXPORT_S3_URL_PROD if self._is_prod else None,
        )
        if not self._is_prod:
            chart_values["push_gateway_url"] = None
        chart_values["localStorage"].update(get_efs_ids(is_prod=self._is_prod))
        return chart_values

    def run(self) -> int:
        self._helm.check_cluster_connectivity()
        img_tag = self._build_and_push_image()
        chart_values = self._get_chart_values(img_tag)
        if self._is_prod:
            self._install_prod(chart_values)
        else:
            self._install_dev(chart_values)
        return 0

    def _install_dev(self, chart_values: dict) -> None:
        namespace = self._namespace
        release = f"{namespace}-{self._NAME}"
        self._helm.upgrade_install_from_local_path(
            release_name=release, namespace=namespace, chart_path=self._CHART_PATH, values=chart_values
        )

    def _install_prod(self, chart_values: dict) -> None:
        if not ChangeHelper.check_git_state():
            return
        chart = HelmChart.for_path(self._CHART_PATH)
        self._helm.check(chart_path=chart.path, values=chart_values)
        deploy_time = utcnow()
        with DeploymentLock.for_deploy(self._NAME, self._deployer):
            self._helm.maybe_publish_chart(chart_path=chart.path, chart_name=chart.name)
            _logger.info(f"Installing {self._NAME} chart v{chart.version} on cluster {self._helm.cluster_name}.")
            exec_result = self._helm.upgrade_install_from_repo(
                release_name=self._NAME, namespace=self._namespace, chart=chart, values=chart_values
            )
        notify_devops_chart_deploy(
            chart=chart,
            exec_result=exec_result,
            deployer=self._deployer,
            deploy_time=deploy_time,
            aws_region=self._aws_region,
            emoji=self._EMOJI,
        )

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)
        parser.add_argument(
            "--prod",
            action="store_true",
            required=False,
            default=False,
            help="Install to remoting prod cluster (defaults to dev).",
        )
        parser.add_argument(
            "--namespace",
            type=str,
            action="store",
            default=None,
            help="namespace to install to",
        )


if __name__ == "__main__":
    BuildAndDeployCacheUsageReporter.start()
