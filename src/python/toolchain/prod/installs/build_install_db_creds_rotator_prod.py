#!/usr/bin/env ./python
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
from argparse import ArgumentParser, Namespace
from pathlib import Path

from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.kubernetes.constants import KubernetesProdNamespaces
from toolchain.prod.builders.build_pex_wrapper import PexWrapperBuilder
from toolchain.util.prod.helm_charts import HelmChart
from toolchain.util.prod.helm_client import HelmClient

_logger = logging.getLogger(__name__)


def get_builder() -> PexWrapperBuilder:
    name = "db_creds_rotator"
    return PexWrapperBuilder(pants_target=f"src/python/toolchain/prod/db_credentials_rotator:{name}", ecr_repo=name)


def get_chart() -> HelmChart:
    return HelmChart.for_path(Path("prod/helm/devops/db-creds-rotator/"))


class BuildAndDeployDBSCredentialsRotatorProd(ToolchainBinary):
    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._builder = get_builder()
        self._dry_run = cmd_args.dry_run
        self._helm = HelmClient(aws_region=cmd_args.aws_region, cluster=HelmClient.Cluster.PROD, dry_run=self._dry_run)
        self._namespace = KubernetesProdNamespaces.PROD if cmd_args.prod else KubernetesProdNamespaces.STAGING
        self._database = cmd_args.database
        self._new_db_host = cmd_args.db_host or None

    def _get_chart_values(self, chart: HelmChart) -> dict:
        chart_values = chart.get_values()
        chart_values.update(database=self._database, new_db_host=self._new_db_host, run_env="prod")
        return chart_values

    def _update_chart(self, img_tag: str) -> HelmChart:
        chart = get_chart()
        values = chart.get_values(with_roundtrip=True)
        values["image"] = img_tag
        chart.save_values(values)
        return chart

    def _install_chart(self, chart: HelmChart) -> None:
        chart_values = self._get_chart_values(chart)
        namespace = self._namespace
        release_name = f"{namespace}-{self._database}-db-creds-rotator"
        self._helm.refresh_repos()
        self._helm.maybe_publish_chart(chart_path=chart.path, chart_name=chart.name)
        self._helm.upgrade_install_from_repo(
            release_name=release_name, namespace=namespace, chart=chart, values=chart_values
        )

    def run(self) -> int:
        img_tag = self._builder.build_and_publish()
        chart = self._update_chart(img_tag)
        self._install_chart(chart)
        return 0

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)
        parser.add_argument("--database", required=True, help="DB to rotate creds for.")
        parser.add_argument(
            "--prod", action="store_true", required=False, default=False, help="Deploy to prod environment"
        )
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
    BuildAndDeployDBSCredentialsRotatorProd.start()
