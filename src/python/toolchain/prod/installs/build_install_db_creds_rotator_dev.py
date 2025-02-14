#!/usr/bin/env ./python
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
from argparse import ArgumentParser, Namespace

from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.prod.installs.build_install_db_creds_rotator_prod import get_builder, get_chart
from toolchain.util.net.net_util import get_remote_username
from toolchain.util.prod.helm_charts import HelmChart
from toolchain.util.prod.helm_client import HelmClient

_logger = logging.getLogger(__name__)


class BuildAndDeployDBSCredentialsRotatorDev(ToolchainBinary):
    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._builder = get_builder()
        # For now (testing) this is hard coded for dev and my namespace
        self._helm = HelmClient(
            aws_region=cmd_args.aws_region, cluster=HelmClient.Cluster.DEV, dry_run=cmd_args.dry_run
        )
        self._namespace = cmd_args.namespace or get_remote_username()
        self._database = cmd_args.database
        self._new_db_host = cmd_args.db_host or None

    def _get_chart_values(self, image_tag: str, chart: HelmChart) -> dict:
        chart_values = chart.get_values()
        chart_values.update(image=image_tag, database=self._database, new_db_host=self._new_db_host, run_env="dev")
        return chart_values

    def run(self) -> int:
        namespace = self._namespace
        img_tag = self._builder.build_and_publish(env_name=f"dev-{namespace}")
        chart = get_chart()
        chart_values = self._get_chart_values(img_tag, chart)
        release = f"{namespace}-{self._database}-db-creds-rotator"
        self._helm.upgrade_install_from_local_path(
            release_name=release, namespace=namespace, chart_path=chart.path, values=chart_values
        )
        return 0

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)
        parser.add_argument("--database", required=True, help="DB to rotate creds for.")
        parser.add_argument("--dry-run", action="store_true", required=False, default=False, help="Do a dry run.")
        parser.add_argument(
            "--namespace", type=str, action="store", default=None, help="Kubernetes namespace to install buildfarm to."
        )
        parser.add_argument(
            "--db-host",
            required=False,
            type=str,
            default=None,
            help="New DB host (if specified, DB host will be update and rotated but not the db user).",
        )


if __name__ == "__main__":
    BuildAndDeployDBSCredentialsRotatorDev.start()
