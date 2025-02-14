#!/usr/bin/env ./python
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
from argparse import ArgumentParser, Namespace
from pathlib import Path

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.constants import ToolchainEnv
from toolchain.kubernetes.constants import KubernetesCluster
from toolchain.prod.installs.install_logging_prod import InstallLoggingProd
from toolchain.prod.tools.deploy_notifications import Deployer, notify_devops_chart_deploy
from toolchain.prod.tools.utils import (
    get_curator_iam_role_arn_for_cluster,
    set_config_values,
    set_fluentbit_service_account_annotation,
)
from toolchain.util.prod.helm_charts import HelmChart
from toolchain.util.prod.helm_client import HelmClient

_logger = logging.getLogger(__name__)


class InstallLoggingDev(ToolchainBinary):
    description = "Install monitoring logging to our DEV Kubernetes cluster."
    _NAMESPACE = "logging"
    _RELEASE_NAME = "dev-logging"
    _INSTALL_TIMEOUT_SEC = 600
    _OPENSEARCH_HOST = "vpc-es-dev-1-rk4lyznh7j3ckq2gp7impmend4.us-east-1.es.amazonaws.com"

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._aws_region = cmd_args.aws_region
        self._helm = HelmClient(
            aws_region=cmd_args.aws_region,
            cluster=KubernetesCluster.DEV,
            dry_run=cmd_args.dry_run,
            keep_helm_files=True,
        )
        self._dry_run = cmd_args.dry_run
        self._helm.check_cluster_connectivity()
        self._deployer = Deployer.get_current()

    def _get_logging_values(self, *, es_curator_image: str) -> dict:
        chart_values = HelmChart.get_chart_values(InstallLoggingProd.LOCAL_CHART_PATH)
        curator_cfg = chart_values["curator"]
        curator_cfg.update(
            image=es_curator_image,
            push_gateway_url=None,
            iam_role_arn=get_curator_iam_role_arn_for_cluster(
                aws_region=self._aws_region, cluster=KubernetesCluster.DEV
            ),
        )

        fluent_bit_cfg = chart_values["fluent-bit"]
        set_fluentbit_service_account_annotation(
            fluent_bit_cfg, aws_region=self._aws_region, cluster=KubernetesCluster.DEV
        )

        opensearch_output_config = fluent_bit_cfg["config"]["outputs"]
        updated_output_cfg = set_config_values(
            opensearch_output_config,
            Host=self._OPENSEARCH_HOST,
            AWS_Region=self._aws_region,
            Logstash_Prefix="dev-logs",
        )
        fluent_bit_cfg["config"]["outputs"] = updated_output_cfg
        chart_values.update(
            toolchain_env=ToolchainEnv.DEV.value,  # type: ignore
            logging_opensearch_host=self._OPENSEARCH_HOST,
        )
        return chart_values

    def _build(self) -> dict:
        es_curator_image = InstallLoggingProd.build_curator("dev")
        return self._get_logging_values(es_curator_image=es_curator_image)

    def _install(self, values: dict, chart_path: Path) -> None:
        chart = HelmChart.for_path(chart_path)
        self._helm.update_dependencies(chart.path)
        deploy_time = utcnow()
        # Disabled for now, helm template thinks we are using k8s 1.16 and fails.
        # self._helm.check(chart_path=chart.path, values=values)
        _logger.info("Installing logging chart to dev cluster")
        exec_result = self._helm.upgrade_install_from_local_path(
            release_name=self._RELEASE_NAME,
            namespace=self._NAMESPACE,
            chart_path=chart_path,
            values=values,
            install_timeout_sec=self._INSTALL_TIMEOUT_SEC,
        )
        notify_devops_chart_deploy(
            chart=chart,
            exec_result=exec_result,
            deployer=self._deployer,
            deploy_time=deploy_time,
            emoji=InstallLoggingProd.EMOJI,
            is_prod=False,
            aws_region=self._aws_region,
        )

    def run(self) -> int:
        self._helm.check_cluster_connectivity()
        values = self._build()
        self._install(values, chart_path=InstallLoggingProd.LOCAL_CHART_PATH)
        return 0

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)
        parser.add_argument("--dry-run", action="store_true", required=False, default=False, help="Dry run.")


if __name__ == "__main__":
    InstallLoggingDev.start()
