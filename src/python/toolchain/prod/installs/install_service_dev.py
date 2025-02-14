#!/usr/bin/env ./python
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
from typing import Any

from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_error import ToolchainAssertion, ToolchainError
from toolchain.config.services import ServiceBuildResult, ServicesBuildResults
from toolchain.constants import ToolchainEnv
from toolchain.kubernetes.cluster import ClusterAPI
from toolchain.prod.tools.changes_helper import ChangeHelper, ChangeLog
from toolchain.prod.tools.deploy_notifications import DeployNotifications, ServiceDeployResult, ServicesDeployResult
from toolchain.prod.tools.resources_resolver import SENTRY_DEV, resolve_resources
from toolchain.prod.tools.utils import Deployer, set_service_iam_role_values
from toolchain.util.prod.helm_charts import ServiceChartInfo
from toolchain.util.prod.helm_client import HelmChart, HelmClient, HelmExecuteResult, TestsResult

_logger = logging.getLogger(__name__)


class InstallServiceDev:
    _TOOLCHAIN_ENV = ToolchainEnv.DEV  # type: ignore

    def __init__(
        self,
        aws_region: str,
        dry_run: bool,
        keep_helm_files: bool = False,
        skip_tests: bool = False,
    ) -> None:
        self._dry_run = dry_run
        self._aws_region = aws_region
        self._helm = HelmClient(
            aws_region=self._aws_region,
            cluster=HelmClient.Cluster.DEV,
            dry_run=dry_run,
            keep_helm_files=keep_helm_files,
        )
        self._skip_tests = skip_tests
        self._sentry_dsn = SENTRY_DEV
        self._helm.check_cluster_connectivity()
        self._deployer = Deployer.get_current()
        self._changes_helper = ChangeHelper.create(aws_region=aws_region)
        self._notifications = DeployNotifications(
            is_prod=False, aws_region=self._aws_region, user=self._deployer.formatted_deployer
        )

    def _get_values(
        self, namespace: str, build_result: ServiceBuildResult, chart_info: ServiceChartInfo
    ) -> dict[str, Any]:
        chart_values = chart_info.get_values()
        chart_values.update(toolchain_env=self._TOOLCHAIN_ENV.value, server_sentry_dsn=self._sentry_dsn)
        if "ingress" in chart_values:
            # Don't install ingress in dev.
            chart_values["ingress"] = {"enabled": False}
        chart_values["global"] = {"region": self._aws_region}
        for chart_parameter in build_result.chart_parameters:
            chart_values[chart_parameter] = {self._aws_region: build_result.revision}

        if build_result.tests_images:
            test_values = chart_values.get("tests")
            if not test_values:
                raise ToolchainAssertion("Test images provided, but not tests object in chart values file.")
            test_values["enabled"] = True
            for image_name, image_version in build_result.tests_images.items():
                if image_name not in test_values:
                    raise ToolchainAssertion(f"No test image {image_name} under chart values tests object.")
                test_values[image_name]["image_rev"] = {self._aws_region: image_version}
        set_service_iam_role_values(
            chart_values, region=self._aws_region, cluster=self._helm.cluster, service=chart_info.chart_name
        )

        if "workers" in chart_values:
            for worker_values in chart_values["workers"].values():
                set_service_iam_role_values(
                    worker_values, region=self._aws_region, cluster=self._helm.cluster, service=chart_info.chart_name
                )
                resolve_resources(
                    service=chart_info.chart_name,
                    aws_region=self._aws_region,
                    toolchain_env=self._TOOLCHAIN_ENV,
                    cluster=self._helm.cluster,
                    namespace=namespace,
                    chart_values=worker_values,
                )
        else:
            if "resources" in chart_values:
                # Hack to limit resource usage of python services in dev.
                rsc_requests = chart_values["resources"]["gunicorn"]["requests"]
                rsc_requests.update(cpu="20m", memory="256Mi")
            resolve_resources(
                service=chart_info.chart_name,
                aws_region=self._aws_region,
                toolchain_env=self._TOOLCHAIN_ENV,
                cluster=self._helm.cluster,
                namespace=namespace,
                chart_values=chart_values,
            )
        return chart_values

    def _validate_namespaces(self, namespaces: set[str]) -> None:
        """Make sure we don't install services to unexpected namespaces."""
        dev_namespaces = ClusterAPI.for_cluster(self._helm.cluster).list_namespaces_of_type("engineer")
        if not namespaces.issubset(dev_namespaces):
            invalid_ns = ", ".join(namespaces - set(dev_namespaces))
            raise ToolchainError(f"Installing services to non-dev namespaces is not allowed: {invalid_ns}")

    def install_services(
        self, namespaces: list[str], build_results: ServicesBuildResults, delete_first: bool = False
    ) -> None:
        self._validate_namespaces(set(namespaces))
        for namespace in namespaces:
            results = []
            if delete_first:
                releases = [
                    f"{namespace}-{ServiceChartInfo.for_service(build_result.service).chart_name}"
                    for build_result in build_results
                ]
                self._helm.uninstall_releases(release_names=releases, namespace=namespace)
            for build_result in build_results:
                deploy_time = utcnow()
                install_result, test_result, change_log = self.install_service(build_result, namespace=namespace)
                results.append(
                    self._result_from_execution(
                        build_result.service.name,
                        build_result.revision,
                        deploy_time,
                        install_result,
                        test_result,
                        change_log,
                    )
                )

            deploy_result = ServicesDeployResult.create(
                deployer=self._deployer,
                cluster=self._helm.cluster,
                namespace=namespace,
                dry_run=False,
                services=results,
            )
            self._notifications.notify_deploy(deploy_result=deploy_result)

    def _result_from_execution(
        self,
        service_name: str,
        revision: str,
        deploy_time: datetime.datetime,
        result: HelmExecuteResult,
        tests: TestsResult,
        change_log: ChangeLog,
    ) -> ServiceDeployResult:
        return ServiceDeployResult(
            service_name=service_name,
            revision=revision,
            success=result.success,
            tests=tests,
            output=result.output,
            deploy_time=deploy_time,
            install_latency=result.latency,
            changes=change_log.get_changes(),
        )

    def install_service(
        self, build_result: ServiceBuildResult, namespace: str
    ) -> tuple[HelmExecuteResult, TestsResult, ChangeLog]:
        chart = ServiceChartInfo.for_service(build_result.service)
        release = f"{namespace}-{chart.chart_name}"
        change_log = self._changes_helper.get_changes_for_service(chart.get_values(), build_result)
        values = self._get_values(namespace, build_result, chart)
        chart_path = chart.chart_path
        if HelmChart.for_path(chart_path).has_depednencies:
            self._helm.update_dependencies(chart.chart_path)
        install_result = self._helm.upgrade_install_from_local_path(
            release_name=release, namespace=namespace, chart_path=chart.chart_path, values=values
        )
        if self._skip_tests:
            test_result = TestsResult.SKIPPED
        else:
            test_result = self._helm.test_release(chart.chart_path, release, namespace)
        dry_run_str = "[dry run]" if self._dry_run else ""
        _logger.info(
            f"Installed {chart.service_name} on {self._helm.cluster_name}/{namespace} "
            f"rev: {build_result.revision} tests: {test_result.value} time took: {install_result.latency.total_seconds()} sec. {dry_run_str}"
        )
        return install_result, test_result, change_log
