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
from toolchain.constants import ToolchainEnv
from toolchain.prod.builders.build_pex_wrapper import PexWrapperBuilder
from toolchain.prod.tools.deploy_notifications import notify_devops_chart_deploy
from toolchain.prod.tools.deployment_lock import DeploymentLock
from toolchain.prod.tools.utils import (
    Deployer,
    get_curator_iam_role_arn_for_cluster,
    get_logging_opensearch_endpoint,
    set_config_values,
    set_fluentbit_service_account_annotation,
)
from toolchain.util.prod.helm_charts import HelmChart
from toolchain.util.prod.helm_client import HelmClient, HelmExecuteResult

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ComponentsVersions:
    logs_curator: str


class InstallLoggingProd(ToolchainBinary):
    description = "Install monitoring logging to our production Kubernetes cluster."
    LOCAL_CHART_PATH = Path("prod/helm/observability/logging")
    _NAMESPACE = "logging"
    _RELEASE_NAME = "prod-logging"
    _INSTALL_TIMEOUT_SEC = 800
    EMOJI = "elastic"
    _CLUSTER_CONFIG = {
        HelmClient.Cluster.PROD: {"log_name": "prod-logs", "curator": True},
        HelmClient.Cluster.REMOTING: {"log_name": "remoting-prod-logs", "curator": False},
    }

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._aws_region = cmd_args.aws_region
        self._deployer = Deployer.get_current()
        self._aws_region = cmd_args.aws_region
        self._silent = cmd_args.silent
        self._cluster = HelmClient.Cluster(cmd_args.cluster) or HelmClient.Cluster.PROD
        self._cluster_config = self._CLUSTER_CONFIG[self._cluster]
        self._helm = HelmClient(
            aws_region=cmd_args.aws_region,
            cluster=self._cluster,
            dry_run=cmd_args.dry_run,
        )
        self._dry_run = cmd_args.dry_run
        self._helm.check_cluster_connectivity()

    def _get_logging_values(self, cluster: str, chart: HelmChart, components: ComponentsVersions) -> dict:
        chart_values = chart.get_values()
        domain_endpoint = get_logging_opensearch_endpoint(self._aws_region)
        _logger.info(f"OpenSearch endpoint: {domain_endpoint}")
        if self._cluster_config["curator"]:
            chart_values["curator"].update(
                image=components.logs_curator,
                enabled=True,
                iam_role_arn=get_curator_iam_role_arn_for_cluster(aws_region=self._aws_region, cluster=self._cluster),
            )
        else:
            chart_values["curator"] = {"enabled": False}
        log_name = self._cluster_config["log_name"]
        fluent_bit_cfg = chart_values["fluent-bit"]
        set_fluentbit_service_account_annotation(fluent_bit_cfg, aws_region=self._aws_region, cluster=self._cluster)

        opensearch_output_config = fluent_bit_cfg["config"]["outputs"]
        updated_output_cfg = set_config_values(
            opensearch_output_config,
            Host=domain_endpoint,
            AWS_Region=self._aws_region,
            Logstash_Prefix=log_name,
        )
        fluent_bit_cfg["config"]["outputs"] = updated_output_cfg
        chart_values.update(
            toolchain_env=ToolchainEnv.PROD.value,  # type: ignore[attr-defined]
            logging_opensearch_host=domain_endpoint,
        )
        return chart_values

    @classmethod
    def build_curator(cls, env_name: str) -> str:
        builder = PexWrapperBuilder(pants_target="src/python/toolchain/prod/elasticsearch_curator:es-curator")
        return builder.build_and_publish(env_name)

    def _build_components(self) -> ComponentsVersions:
        es_curator_image = self.build_curator("prod")
        return ComponentsVersions(logs_curator=es_curator_image)

    def _publish_and_install(self, chart: HelmChart, values: dict) -> tuple[HelmExecuteResult, datetime.datetime]:
        deploy_time = utcnow()
        # Disabled for now, helm template thinks we are using k8s 1.16 and fails.
        # self._helm.check(chart_path=chart.path, values=values)
        self._helm.maybe_publish_chart(chart_path=chart.path, chart_name=chart.name)
        _logger.info(f"Installing logging chart v{chart.version} on prod cluster. dry_run={self._dry_run}")
        exec_result = self._helm.upgrade_install_from_repo(
            release_name=self._RELEASE_NAME,
            namespace=self._NAMESPACE,
            chart=chart,
            values=values,
            install_timeout_sec=self._INSTALL_TIMEOUT_SEC,
        )
        return exec_result, deploy_time

    def run(self) -> int:
        components = self._build_components()
        chart = HelmChart.for_path(self.LOCAL_CHART_PATH)
        values = self._get_logging_values(self._helm.cluster_name, chart, components)

        self._helm.update_dependencies(chart.path)
        with DeploymentLock.for_deploy("logging", self._deployer):
            exec_result, deploy_time = self._publish_and_install(chart, values=values)
        notify_devops_chart_deploy(
            chart=chart,
            exec_result=exec_result,
            deployer=self._deployer,
            deploy_time=deploy_time,
            aws_region=self._aws_region,
            emoji=self.EMOJI,
            silent=self._silent,
        )
        return 0

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)
        parser.add_argument("--dry-run", action="store_true", required=False, default=False, help="Dry run.")
        parser.add_argument(
            "--silent", action="store_true", required=False, default=False, help="Notity alerts chat room."
        )
        parser.add_argument(
            "--cluster", action="store", required=False, help="Cluster into which to install logging stack"
        )


if __name__ == "__main__":
    InstallLoggingProd.start()
