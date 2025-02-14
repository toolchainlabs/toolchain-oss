#!/usr/bin/env ./python
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
from argparse import ArgumentParser, Namespace
from pathlib import Path

from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.util.net.net_util import get_remote_username
from toolchain.util.prod.helm_charts import HelmChart
from toolchain.util.prod.helm_client import HelmClient, HelmExecuteResult

_logger = logging.getLogger(__name__)


class InstallBuildboxWorkersDev(ToolchainBinary):
    description = "Install BuildBox workers chart to our DEV Kubernetes cluster."
    _LOCAL_CHART_PATH = Path("prod/helm/services/remoting/buildbox")
    # 5m since the workers download images from s3 as part of the init process and that can take some time.
    _INSTALL_TIMEOUT_SEC = 600

    # Workers need to know what instance name to connect for.
    # The ID can be located via the toolshed dev instance. http://localhost:9600/db/users/admin/site/customer/
    _INSTANCE_NAMES = {
        "asher": "hdt2hniUXemsaHDuiBap4B",
        "stuhood": "fTSFtcU7EmQhgV5HUv5WnS",
    }

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._aws_region = cmd_args.aws_region
        self._namespace = cmd_args.namespace or get_remote_username()
        self._helm = HelmClient(
            aws_region=cmd_args.aws_region,
            cluster=HelmClient.Cluster.DEV,
            dry_run=cmd_args.dry_run,
        )
        self._dry_run = cmd_args.dry_run
        self._helm.check_cluster_connectivity()
        self._instance_name = self._INSTANCE_NAMES.get(self._namespace)
        if not self._instance_name:
            raise ToolchainAssertion(
                f"Unknown instance name for namespace {self._namespace} in dev. To fix this add the customer ID for the org/customer in your dev environment to InstallBuildboxWorkersDev._INSTANCE_NAMES. "
                "To find that ID you can access the customer table via Toolshed (http://localhost:9600/db/users/admin/site/customer/)."
            )
        _logger.info(f"Using instance name: {self._instance_name} for namespace: {self._namespace}")

    def _install_upgrade_buildbox_workers(self) -> HelmExecuteResult:
        _logger.info("Installing BuildBox worker chart to dev cluster")
        values = HelmChart.get_chart_values(self._LOCAL_CHART_PATH)
        values.update(
            mainInstanceName=self._instance_name,
            customer=self._namespace,
            # Note that we don't use `grpcs` in dev because SSL isn't installed.
            endpoint=f"grpc://remoting-workers-proxy-server.{self._namespace}.svc.cluster.local:8981",
        )
        return self._helm.upgrade_install_from_local_path(
            release_name=f"{self._namespace}-buildbox-workers",
            namespace=self._namespace,
            chart_path=self._LOCAL_CHART_PATH,
            values=values,
            install_timeout_sec=self._INSTALL_TIMEOUT_SEC,
        )

    def run(self) -> int:
        self._install_upgrade_buildbox_workers()
        return 0

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)
        parser.add_argument(
            "--namespace",
            type=str,
            action="store",
            default=None,
            help="Kubernetes namespace to install Builbox workers to.",
        )
        parser.add_argument("--dry-run", action="store_true", required=False, default=False, help="Dry run.")


if __name__ == "__main__":
    InstallBuildboxWorkersDev.start()
