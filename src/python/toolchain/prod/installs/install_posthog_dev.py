#!/usr/bin/env ./python
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from pathlib import Path

from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.constants import ToolchainEnv
from toolchain.prod.tools.resources_resolver import get_redis_host_for_env
from toolchain.prod.tools.utils import Deployer
from toolchain.util.net.net_util import get_remote_username
from toolchain.util.prod.helm_charts import HelmChart
from toolchain.util.prod.helm_client import HelmClient


class InstalPosthogDev(ToolchainBinary):
    _CHART_PATH = Path("prod/helm/tools/posthog/")

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._aws_region = cmd_args.aws_region
        self._namespace = cmd_args.namespace or get_remote_username()
        self._helm = HelmClient(
            aws_region=self._aws_region,
            cluster=HelmClient.Cluster.DEV,
            dry_run=False,
            keep_helm_files=cmd_args.keep_helm_files,
        )
        self._deployer = Deployer.get_current()
        self._helm.check_cluster_connectivity()

    def update_values(self, values: dict) -> None:
        # this only works for dev, for prod it will return the remoting cache redis instance which is not good.
        values["redis"]["host"] = get_redis_host_for_env(ToolchainEnv.DEV)  # type: ignore[attr-defined]

    def run(self) -> int:
        chart = HelmChart.for_path(self._CHART_PATH)
        values = chart.get_values()
        self.update_values(values)
        self._helm.check(chart_path=chart.path, values=values)
        self._helm.upgrade_install_from_local_path(
            release_name=f"{self._namespace}-posthog-dev",
            namespace=self._namespace,
            chart_path=chart.path,
            values=values,
        )
        return 0

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        super().add_arguments(parser)
        cls.add_aws_region_argument(parser)
        parser.add_argument(
            "--namespace", type=str, action="store", default=None, help="Kubernetes namespace to install posthog to."
        )
        parser.add_argument(
            "--keep-helm-files", action="store_true", required=False, default=False, help="Keep Helm values file."
        )


if __name__ == "__main__":
    InstalPosthogDev.start()
