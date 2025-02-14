# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import logging
import os
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePath
from typing import Any

from packaging.version import Version
from ruamel.yaml import YAML

from toolchain.base.datetime_tools import utcnow
from toolchain.base.fileutil import safe_delete_dir, safe_delete_file
from toolchain.base.toolchain_error import ToolchainAssertion, ToolchainError
from toolchain.kubernetes.cluster import ClusterAPI
from toolchain.kubernetes.constants import KubernetesCluster
from toolchain.util.prod.exceptions import NotConnectedToClusterError
from toolchain.util.prod.helm_charts import HelmChart, RemoteHelmChart

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HelmExecuteResult:
    cluster: KubernetesCluster
    namespace: str | None
    command: str
    command_line: str
    dry_run: bool
    success: bool
    output: str
    start: datetime.datetime
    end: datetime.datetime

    @property
    def latency(self):
        return self.end - self.start

    def get_json(self) -> Any:
        return json.loads(self.output)

    def get_lines(self) -> list[str]:
        return self.output.splitlines()

    def get_value(self, key: str) -> str | None:
        for line in self.get_lines():
            curr_key, _, value = line.partition(":")
            if curr_key and curr_key.strip().lower() == key:
                return value
        return None


class HelmExcutionException(ToolchainError):
    def __init__(self, error_message, execute_result):
        super().__init__(error_message)
        self._result = execute_result

    @property
    def execute_result(self):
        return self._result


class TestsResult(Enum):
    PASS = "pass"
    FAIL = "fail"
    NO_TESTS = "NA"
    SKIPPED = "skipped"


class HelmClient:
    Cluster = KubernetesCluster
    _REQUIRED_HELM_VERSION = Version("3.11.0")
    K8S_VERSION = "1.23"  # TODO: accept this as a param from the caller which will get it from the k8s api
    TOOLCHAIN_REPO = "helm-e1"
    _INSTALL_TIMEOUT_SEC = 90
    _TESTS_FOLDER = "templates/tests"
    _HELM_EXECUTABLE = "helm"
    _DRY_RUN_CMDS = ["install", "upgrade"]

    def __init__(
        self,
        aws_region: str,
        cluster: KubernetesCluster,
        dry_run: bool = False,
        keep_helm_files: bool = False,
    ) -> None:
        self._cluster = cluster
        self._region_name = aws_region
        self._dry_run = dry_run
        self._keep_helm_files = keep_helm_files
        self._checked_version = False

    def check_helm_version(self) -> None:
        self._checked_version = True
        output = self._execute_helm("version", cmd_args=["--short"]).output
        version = Version(output.strip()[1:])
        if version < self._REQUIRED_HELM_VERSION:
            raise ToolchainAssertion(
                f"Must use helm version {self._REQUIRED_HELM_VERSION} or higher. You have {output}"
            )

    def check_cluster_connectivity(self) -> None:
        self.check_helm_version()
        if not ClusterAPI.is_connected_to_cluster(self.cluster):
            raise NotConnectedToClusterError(self.cluster)

    def _list_repos(self) -> tuple[str, ...]:
        repos = self._execute_helm("repo", ["list", "--output", "json"]).get_json()
        return tuple(rel["name"] for rel in repos)

    def _list_releases(self, namespace: str) -> tuple[str, ...]:
        releases = self._execute_helm("list", ["--output", "json"], namespace=namespace).get_json()
        return tuple(rel["name"] for rel in releases)

    @property
    def cluster(self) -> KubernetesCluster:
        return self._cluster

    @property
    def cluster_name(self) -> str:
        return self._cluster.value

    def refresh_repos(self) -> None:
        self._execute_helm("repo", ["update"])

    def get_repo_version(self, chart_name: str) -> str | None:
        """Searches for available packages/charts in our repo."""
        full_chart_name = f"{self.TOOLCHAIN_REPO}/{chart_name}"

        charts: list[dict] = self._execute_helm("search", ["repo", full_chart_name, "--output", "json"]).get_json()

        # `helm search` does a keyword search so charts with same prefix will end up in results.
        # Filter results to the exact chart name.
        charts = [c for c in charts if c["name"] == full_chart_name]

        if len(charts) < 1:
            return None
        if len(charts) > 1:
            raise ToolchainAssertion("more than one chart...")
        return charts[0]["version"]

    def _has_tests(self, chart_path: Path) -> bool:
        tests_path = os.path.join(chart_path, self._TESTS_FOLDER)
        return bool(os.path.exists(tests_path) and os.listdir(tests_path))

    def test_release(
        self, chart_path: Path, release_name: str, namespace: str, timeout_sec: str | int | None = None
    ) -> TestsResult:
        if not self._has_tests(chart_path):
            return TestsResult.NO_TESTS
        timeout_sec = timeout_sec or "60"
        _logger.info(f"Helm Test Release: {release_name}, timeout: {timeout_sec}sec")
        try:
            exec_result = self._execute_helm(
                "test", cmd_args=[release_name, "--timeout", f"{timeout_sec}s"], namespace=namespace
            )
        except HelmExcutionException as error:
            exec_result = error.execute_result
            _logger.warning(f"helm test failed: {exec_result.output}")
            return TestsResult.FAIL
        result = exec_result.get_value("phase")
        if not result:
            _logger.warning(f"[helm test] Unexpected output: {exec_result.output}")
            return TestsResult.FAIL
        success = result.strip().lower() == "succeeded"
        if not success:
            _logger.warning(f"helm test failed: {exec_result.output}")
        return TestsResult.PASS if success else TestsResult.FAIL

    def upgrade_install_from_repo(
        self,
        *,
        release_name: str,
        namespace: str,
        chart: HelmChart | RemoteHelmChart,
        values: dict,
        repo: str = TOOLCHAIN_REPO,
        wait_for_ready: bool = True,
        install_timeout_sec: int | None = None,
    ) -> HelmExecuteResult:
        chart_full_name = f"{repo}/{chart.name}"
        cmd_args = ["--version", chart.version]
        _logger.debug(f"Installing chart {chart_full_name} v{chart.version} on {self._cluster} dry_run={self._dry_run}")
        return self._upgrade_install_chart(
            chart=chart_full_name,
            release_name=release_name,
            namespace=namespace,
            values=values,
            cmd_args=cmd_args,
            wait_for_ready=wait_for_ready,
            install_timeout_sec=install_timeout_sec,
        )

    def upgrade_install_from_local_path(
        self,
        *,
        release_name: str,
        namespace: str,
        chart_path: Path,
        values: dict,
        install_timeout_sec: int | None = None,
    ) -> HelmExecuteResult:
        _logger.debug(f"Installing local chart {chart_path} on {self._cluster} dry_run={self._dry_run}")
        return self._upgrade_install_chart(
            chart=chart_path.as_posix(),
            release_name=release_name,
            namespace=namespace,
            values=values,
            wait_for_ready=True,
            cmd_args=[],
            install_timeout_sec=install_timeout_sec,
        )

    def maybe_publish_chart(self, chart_path: Path, chart_name: str) -> str:
        if self.TOOLCHAIN_REPO not in self._list_repos():
            raise ToolchainAssertion("Toolchain Helm repo wasn't added to helm.")
        version = HelmChart.for_path(chart_path).version
        if self.get_repo_version(chart_name) == version:
            _logger.debug(f"chart {chart_name} v{version} already published to helm repo.")
            return version
        if self._dry_run:
            _logger.info(f"Would have published {chart_name} v{version} from {chart_path} to helm charts repo.")
        else:
            self._publish_chart(chart_path=chart_path, version=version, prefix=chart_name)
        return version

    def _publish_chart(self, *, chart_path: Path, version: str, prefix: str) -> None:
        helm_repo = self.TOOLCHAIN_REPO
        _logger.info(f"Publishing chart {chart_path} v{version} to {helm_repo}")
        with tempfile.TemporaryDirectory() as tmpdir:
            self._execute_helm("package", ["-d", tmpdir, str(chart_path)])
            package = os.path.join(tmpdir, f"{prefix}-{version}.tgz")
            self._execute_helm("s3", ["push", package, helm_repo])

    def uninstall_releases(self, release_names: list[str], namespace: str) -> HelmExecuteResult | None:
        releases_to_delete = set(release_names).intersection(self._list_releases(namespace))
        if not releases_to_delete:
            return None
        releases_str = ", ".join(releases_to_delete)
        _logger.info(f"Uninstalling helm releases: {releases_str}")
        cmd_args = list(releases_to_delete)
        cmd_args.extend(("--timeout", "3m"))
        return self._execute_helm("uninstall", cmd_args=cmd_args)

    def update_dependencies(self, chart_path: Path) -> None:
        if not HelmChart.for_path(chart_path).has_depednencies:
            _logger.warning(
                f"Chart {chart_path} doesn't have dependencies. ignoreing call to `update_dependencies` - consider removing it."
            )
            return
        self.refresh_repos()
        _logger.debug(f"Updating dependencies for chart {chart_path}")
        safe_delete_dir(chart_path / "charts")
        safe_delete_file(chart_path / "requirements.lock")
        self._execute_helm("dependency", ["update", chart_path.as_posix()])

    def check(self, chart_path: PurePath, values: dict) -> HelmExecuteResult:
        with self._with_values(values) as values_file:
            all_args = [chart_path.as_posix(), "--debug", "--values", values_file, "--kube-version", self.K8S_VERSION]
            result = self._execute_helm("template", cmd_args=all_args)
            return result

    def _upgrade_install_chart(
        self,
        chart: str,
        release_name: str,
        namespace: str,
        values: dict,
        cmd_args: list[str] | None,
        wait_for_ready: bool,
        install_timeout_sec: int | None,
    ) -> HelmExecuteResult:
        with self._with_values(values) as values_file:
            all_args = ["--install", release_name, chart, "--debug", "--values", values_file]
            if wait_for_ready:
                all_args.extend(["--wait", "--timeout", f"{install_timeout_sec or self._INSTALL_TIMEOUT_SEC}s"])
            all_args.extend(cmd_args or [])
            result = self._execute_helm("upgrade", cmd_args=all_args, namespace=namespace)
            _logger.info(f"Installed {chart} {release_name} on {self._cluster.value} dry_run={self._dry_run}")
            return result

    @contextmanager
    def _with_values(self, values: dict):
        with tempfile.NamedTemporaryFile(mode="w", delete=not self._keep_helm_files) as tf:
            if self._keep_helm_files:
                _logger.info(f"Helm values.yaml path: {tf.name}")
            YAML(typ="safe").dump(values, stream=tf)
            tf.flush()
            yield tf.name

    def _execute_helm(self, helm_cmd: str, cmd_args: list[str], namespace: str | None = None) -> HelmExecuteResult:
        if not self._checked_version:
            raise ToolchainAssertion(
                "Must call HelmClient.check_cluster_connectivity() or HelmClient.check_helm_version() before running helm commands."
            )
        cmd = [self._HELM_EXECUTABLE, helm_cmd]
        cmd.extend(cmd_args)
        cmd.extend([f"--kube-context={self._cluster.value}"])
        if namespace:
            cmd.extend(["--namespace", namespace])
        use_dry_run = helm_cmd in self._DRY_RUN_CMDS and self._dry_run
        if use_dry_run:
            cmd.append("--dry-run")
        cmd_str = " ".join(cmd)
        start = utcnow()
        new_nev = os.environ.copy()
        new_nev.update({"HELM_S3_MODE": "3"})  # Make sure the helm s3 plugin knows we are using Helm v3)
        try:
            output = subprocess.check_output(cmd, env=new_nev).decode("utf8")
        except subprocess.CalledProcessError as error:
            end = utcnow()
            _logger.exception(f"Execute helm failed: {cmd_str}")
            output = ((error.stderr or b"") + (error.stdout or b"")).decode()  # type: ignore
            result = HelmExecuteResult(
                cluster=self.cluster,
                namespace=namespace,
                command=helm_cmd,
                command_line=cmd_str,
                dry_run=use_dry_run,
                success=False,
                output=output,
                start=start,
                end=end,
            )
            raise HelmExcutionException("Helm command failed", execute_result=result)
        end = utcnow()
        _logger.debug(output)
        return HelmExecuteResult(
            cluster=self.cluster,
            namespace=namespace,
            command=helm_cmd,
            command_line=cmd_str,
            dry_run=use_dry_run,
            success=True,
            output=output,
            start=start,
            end=end,
        )
