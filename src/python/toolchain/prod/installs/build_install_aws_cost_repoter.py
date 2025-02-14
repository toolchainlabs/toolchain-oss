#!/usr/bin/env ./python
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
from argparse import ArgumentParser, Namespace
from pathlib import Path

from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.prod.builders.build_pex_wrapper import PexWrapperBuilder
from toolchain.prod.tools.utils import get_slack_webhook_url
from toolchain.util.prod.helm_charts import HelmChart
from toolchain.util.prod.helm_client import HelmClient

_logger = logging.getLogger(__name__)


class BuildAndDeployAWSCostReporter(ToolchainBinary):
    _PEX_TARGET = "src/python/toolchain/prod/aws_cost_reporter:aws_cost_reporter_tool"
    _CHART_PATH = Path("prod/helm/devops/aws-cost-reporter/")

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._aws_region = cmd_args.aws_region
        self._helm = HelmClient(
            aws_region=cmd_args.aws_region, cluster=HelmClient.Cluster.DEV, dry_run=cmd_args.dry_run
        )
        self._namespace = "devops"

    def _build_and_push_image(self) -> str:
        builder = PexWrapperBuilder(pants_target=self._PEX_TARGET)
        return builder.build_and_publish()

    def _get_chart_values(self, image_tag: str) -> dict:
        chart_values = HelmChart.get_chart_values(self._CHART_PATH)

        chart_values.update(image=image_tag, slack_webhook=get_slack_webhook_url(self._aws_region))
        return chart_values

    def run(self) -> int:
        namespace = self._namespace
        self._helm.check_cluster_connectivity()
        img_tag = self._build_and_push_image()
        chart_values = self._get_chart_values(img_tag)
        release = f"{namespace}-aws-cost-reporter"
        self._helm.upgrade_install_from_local_path(
            release_name=release, namespace=namespace, chart_path=self._CHART_PATH, values=chart_values
        )
        return 0

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)
        parser.add_argument("--dry-run", action="store_true", required=False, default=False, help="Do a dry run.")


if __name__ == "__main__":
    BuildAndDeployAWSCostReporter.start()
