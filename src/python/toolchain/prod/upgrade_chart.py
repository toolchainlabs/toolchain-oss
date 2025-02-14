#!/usr/bin/env ./python
# Copyright 2023 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from argparse import ArgumentParser, Namespace
from pathlib import Path
from urllib.parse import urljoin

import httpx
from packaging import version
from ruamel import yaml

from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.prod.installs.install_aws_alb_ingress_controller import AwsAlbIngressControllerChartInstaller
from toolchain.prod.installs.install_aws_efs_driver import InstallAwsEFSDriver
from toolchain.prod.installs.install_external_dns_prod import ExternalDNSChartInstaller
from toolchain.prod.installs.install_grafana_prod import InstallGrafanaProd
from toolchain.prod.installs.install_influxdb import InstallAndBootstrapInfluxDB
from toolchain.prod.installs.install_logging_prod import InstallLoggingProd
from toolchain.prod.installs.install_monitoring_prod import InstallMonitoringProd
from toolchain.util.prod.helm_charts import HelmChart

_logger = logging.getLogger(__name__)


class UpgradeHelmChart(ToolchainBinary):
    CHARTS = {
        "monitoring": InstallMonitoringProd.LOCAL_CHART_PATH,
        "grafana": InstallGrafanaProd.LOCAL_CHART_PATH,
        "logging": InstallLoggingProd.LOCAL_CHART_PATH,
        "aws-alb": AwsAlbIngressControllerChartInstaller.LOCAL_CHART_PATH,
        "aws-efs": InstallAwsEFSDriver.LOCAL_CHART_PATH,
        "external-dns": ExternalDNSChartInstaller.LOCAL_CHART_PATH,
        "dashboard": Path("prod/helm/devops/kubernetes-dashboard"),
        "dev-prometheus": Path("prod/helm/dev-support/dev-prometheus"),
        "autoscaler": Path("prod/helm/devops/cluster-autoscaler"),
        "influxdb": InstallAndBootstrapInfluxDB.LOCAL_CHART_PATH,
    }

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._yaml_cache: dict[str, dict] = {}
        self._check_only = cmd_args.check
        charts = [cmd_args.chart] if cmd_args.chart else sorted(self.CHARTS.keys())
        self._chart_paths = tuple(self.CHARTS[chart] for chart in charts)

    def run(self) -> int:
        for chart_path in self._chart_paths:
            self.generic_chart_updater(chart_path, check_only=self._check_only)
        return 0

    def _get_yaml(self, url: str) -> dict:
        if url in self._yaml_cache:
            return self._yaml_cache[url]
        _logger.debug(f"get yaml: {url}")
        resp = httpx.get(url)
        resp.raise_for_status()
        yaml_data = yaml.safe_load(resp.content)
        self._yaml_cache[url] = yaml_data
        return yaml_data

    def generic_chart_updater(self, cp: Path, check_only: bool = False) -> bool:
        chart = HelmChart.for_path(cp)
        manifest = chart.get_chart_manifest(with_roundtrip=True)
        updated = self.update_from_dependencies(manifest)
        if check_only:
            return updated
        if not updated:
            return False
        ver = version.parse(manifest["version"]).release
        if not ver:
            raise ToolchainAssertion(f"Failed to parse version: {manifest['version']}")
        chart_version = list(ver)
        chart_version[1] = chart_version[1] + 1
        manifest["version"] = ".".join(str(part) for part in chart_version)
        chart.save_chart_manifest(manifest)
        return True

    def iter_external_dependencies(self, manifest):
        for dependency in manifest["dependencies"]:
            repo = dependency["repository"]
            if not repo.startswith("https://"):
                continue
            yield dependency

    def _get_external_repo_charts(self, repo: str):
        if not repo.endswith("/"):
            repo = f"{repo}/"
        index = self._get_yaml(urljoin(repo, "index.yaml"))
        return index["entries"]

    def update_from_dependencies(self, manifest: dict):
        is_first = True
        updated = False
        for dependency in self.iter_external_dependencies(manifest):
            charts = self._get_external_repo_charts(dependency["repository"])
            name = dependency["name"]
            current_ver = dependency["version"]
            latest = charts[name][0]
            latest_ver = latest["version"]
            if latest_ver == current_ver:
                _logger.info(f"{name} - on latest version: {current_ver=}")
                continue
            updated = True
            _logger.info(f"update {name} chart dependency from {current_ver} to {latest_ver}")
            dependency["version"] = latest_ver
            if is_first:
                latest_app_ver = latest["appVersion"]
                _logger.info(f"update app version (from {name}) from {manifest['appVersion']} to {latest_app_ver}")
                manifest["appVersion"] = latest_app_ver
                is_first = False
        return updated

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        parser.add_argument(
            "chart",
            choices=tuple(sorted(cls.CHARTS.keys())),
            nargs="?",
            default=None,
            help="Chart to upgrade (defaults to all, only one chart can be specified)",
        )
        parser.add_argument(
            "--check", action="store_true", required=False, default=False, help="check if upgrade is needed."
        )


if __name__ == "__main__":
    UpgradeHelmChart.start()
