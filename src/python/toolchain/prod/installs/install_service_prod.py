#!/usr/bin/env ./python
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from argparse import ArgumentParser, Namespace
from collections.abc import Sequence
from enum import Enum, unique

from toolchain.aws.acm import ACM
from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.config.services import ToolchainService, extrapolate_services, get_channel_for_cluster
from toolchain.constants import ToolchainEnv
from toolchain.kubernetes.constants import KubernetesCluster, KubernetesProdNamespaces, get_namespaces_for_prod_cluster
from toolchain.prod.tools.changes_helper import ChangeHelper
from toolchain.prod.tools.deploy_notifications import DeployNotifications, ServiceDeployResult, ServicesDeployResult
from toolchain.prod.tools.deployment_lock import DeploymentLock
from toolchain.prod.tools.resources_resolver import SENTRY_PROD, resolve_resources
from toolchain.prod.tools.utils import (
    Deployer,
    IngressType,
    get_cluster,
    get_ingress_security_group_id,
    get_namespace_for_cmd_args,
    set_service_iam_role_values,
)
from toolchain.util.prod.chat_client import Channel
from toolchain.util.prod.helm_charts import HelmChart, ServiceChartInfo
from toolchain.util.prod.helm_client import HelmClient, TestsResult

_logger = logging.getLogger(__name__)


@unique
class IngressMode(Enum):
    PUBLIC = "public"  # default
    PRIVATE = "private"  # Always use the private (behind a VPN ingress)

    def get_ingress_type(self) -> IngressType:
        if self == self.PUBLIC:
            return IngressType.PUBLIC
        if self == self.PRIVATE:
            return IngressType.PRIVATE
        raise ToolchainAssertion("Invalid Ingress Mode.")


def get_git_skip_note() -> str:
    print(
        "`--ignore-git-check` used. This is generally not safe and should only be used in emergencies.\nYou should deploy from `master`."
    )
    reason = input("Please provide a reason for using this flag: ").strip()
    if len(reason) < 7:
        raise ToolchainAssertion("Please provide a valid reason (at least 7 characters)")
    return f"Skip git check: {reason}"


class InstallServiceProd:
    _TOOLCHAIN_ENV = ToolchainEnv.PROD  # type: ignore
    _DEFAULT_REPLICAS_BY_NS = {
        KubernetesProdNamespaces.PROD: 3,
        KubernetesProdNamespaces.STAGING: 1,
        KubernetesProdNamespaces.EDGE: 1,
    }

    def __init__(
        self,
        *,
        aws_region: str,
        dry_run: bool,
        namespace: str,
        cluster: KubernetesCluster,
        silent: bool = False,
        emoji: str | None = None,
        keep_helm_files: bool = False,
        skip_tests: bool = False,
    ) -> None:
        self._dry_run = dry_run
        self._silent = silent
        self._cluster = cluster
        self._deployer = Deployer.get_current()
        if namespace not in get_namespaces_for_prod_cluster(self._cluster):
            raise ToolchainAssertion(f"Invalid namespace specified: {namespace}")
        self._namespace = namespace
        self._host_name_prefix = "staging" if KubernetesProdNamespaces.is_staging(self._namespace) else ""
        if KubernetesProdNamespaces.is_prod(self._namespace) and silent:
            raise ToolchainAssertion("Silent mode not allowed when installing to prod.")
        self._aws_region = aws_region
        self._helm = HelmClient(
            aws_region=aws_region,
            dry_run=self._dry_run,
            cluster=cluster,
            keep_helm_files=keep_helm_files,
        )
        self._notifications = DeployNotifications(
            is_prod=True, aws_region=aws_region, user=self._deployer.formatted_deployer
        )
        self._sentry_dsn = SENTRY_PROD
        self._helm.check_cluster_connectivity()
        self._emoji = emoji
        channel_name = get_channel_for_cluster(cluster)
        self._notify_channel = Channel(channel_name) if channel_name else None
        self._skip_tests = skip_tests
        self._notes: list[str] = []

    def _get_domain(self, ingress_cfg: dict) -> str:
        domains = []
        for rule in ingress_cfg["rules"]:
            host = rule["host"]
            if "www." in host:
                continue
            domains.append(host)
        if len(domains) != 1:
            raise ToolchainAssertion(f"Unexpected domains in rules {domains}")
        return domains[0]

    def _update_rules(self, ingress_cfg: dict) -> None:
        if not self._host_name_prefix:
            return
        for rule in ingress_cfg["rules"]:
            host = rule["host"]
            rule["host"] = f"{self._host_name_prefix}.{host}"

    def _resolve_ingress(self, chart_values: dict, cluster: KubernetesCluster, chart: ServiceChartInfo) -> bool:
        if "ingress" not in chart_values:
            return False
        ingress_mode = IngressMode(chart.service_config.get("ingress", IngressMode.PUBLIC.value))
        ingress_type = ingress_mode.get_ingress_type()
        ingress_cfg = chart_values["ingress"]
        self._update_rules(ingress_cfg)
        ingress_cfg["enabled"] = True
        domain_name = self._get_domain(ingress_cfg)
        cert_arn = ACM(self._aws_region).get_cert_arn_for_domain(domain_name)
        if not cert_arn:
            raise ToolchainAssertion(f"Couldn't find cert for {domain_name}")
        security_group_id = get_ingress_security_group_id(self._aws_region, cluster, ingress_type)
        if not security_group_id:
            raise ToolchainAssertion(f"Couldn't find security group for cluster: {cluster.value}")
        ingress_cfg.update(
            scheme="internet-facing" if ingress_type == IngressType.PUBLIC else "internal",
            ssl_certificate_arn={self._aws_region: cert_arn},
            external_ingress_sg_id={self._aws_region: security_group_id},
            logs_prefix=cluster.value,
        )
        return True

    def calculate_values(self, chart: ServiceChartInfo) -> tuple[dict, bool, int]:
        namespace = self._namespace
        chart_values = chart.get_values()
        cluster = self._helm.cluster
        chart_values["global"] = {"region": self._aws_region}
        is_workflow = "workers" in chart_values
        replicas_config = chart.service_config.get("replicas", self._DEFAULT_REPLICAS_BY_NS)  # type: ignore[call-overload,arg-type]
        replicas = replicas_config.get(self._namespace, self._DEFAULT_REPLICAS_BY_NS[self._namespace])  # type: ignore[attr-defined]
        chart_values.update(
            server_sentry_dsn=self._sentry_dsn,
            toolchain_env=self._TOOLCHAIN_ENV.value,
        )

        set_service_iam_role_values(chart_values, region=self._aws_region, cluster=cluster, service=chart.chart_name)
        if is_workflow:
            if KubernetesProdNamespaces.is_prod(namespace):
                # We don't have a solution for testing workflow services in staging/prod yet.
                # so we don't deploy them to prod.
                raise ToolchainAssertion("Workflow services shouldn't be deployed to prod namespace.")
            for worker_values in chart_values["workers"].values():
                set_service_iam_role_values(
                    worker_values, region=self._aws_region, cluster=cluster, service=chart.chart_name
                )
                worker_values["replicas"] = replicas
                resolve_resources(
                    service=chart.chart_name,
                    aws_region=self._aws_region,
                    toolchain_env=self._TOOLCHAIN_ENV,
                    cluster=self._helm.cluster,
                    namespace=namespace,
                    chart_values=worker_values,
                )
        else:
            chart_values["replicas"] = replicas
            resolve_resources(
                service=chart.chart_name,
                aws_region=self._aws_region,
                toolchain_env=self._TOOLCHAIN_ENV,
                cluster=self._helm.cluster,
                namespace=namespace,
                chart_values=chart_values,
            )
        has_ingress = self._resolve_ingress(chart_values, cluster, chart)
        test_enabled = chart_values.get("tests", {}).get("enabled", True)
        # if there is an ingress, the AWS ALB ingress controller has to update AWS ALB Target groups as pods spin up (and spin down) and that takes more time.
        # Hence a longer timeout per pod if there in an ingress.
        install_timeout = (90 if has_ingress else 45) * replicas
        return chart_values, test_enabled, install_timeout

    def _publish_and_install(self, services: Sequence[ToolchainService]) -> list[ServiceDeployResult]:
        chart_versions = self._publish_charts(services)
        results = []
        for chart, chart_version in chart_versions.items():
            service_deploy = self._install_service(chart, chart_version)
            results.append(service_deploy)
        return results

    def install_services(self, services: Sequence[ToolchainService], notes: list[str]) -> None:
        results = []
        services_list = ", ".join(svc.name for svc in services)
        cluster = self._helm.cluster
        _logger.info(
            f"Installing services: {services_list} into {cluster.value}/{self._namespace} dry run: {self._dry_run}"
        )
        # For now, we lock all services. in the future, we might want to fragment that and lock specific services.
        with DeploymentLock.for_deploy(f"services-{cluster.value}", self._deployer):
            results = self._publish_and_install(services)
        deploy_result = ServicesDeployResult.create(
            deployer=self._deployer,
            cluster=cluster,
            namespace=self._namespace,
            dry_run=self._dry_run,
            services=results,
            notes=notes,
        )
        self._notifications.notify_deploy(
            deploy_result=deploy_result, quiet=self._silent, emoji=self._emoji, channel=self._notify_channel
        )

    def _publish_charts(self, services: Sequence[ToolchainService]) -> dict[ServiceChartInfo, str]:
        self._helm.refresh_repos()
        chart_versions = {}
        for service in services:
            chart = ServiceChartInfo.for_service(service)
            chart_path = chart.chart_path
            if HelmChart.for_path(chart_path).has_depednencies:
                self._helm.update_dependencies(chart_path)
            chart_version = self._helm.maybe_publish_chart(chart_path=chart_path, chart_name=chart.chart_name)
            chart_versions[chart] = chart_version
        return chart_versions

    def _install_service(self, service_chart: ServiceChartInfo, version: str) -> ServiceDeployResult:
        namespace = self._namespace
        values, tests_enabled, install_timeout = self.calculate_values(service_chart)
        chart = HelmChart.for_path(service_chart.chart_path)
        deploy_time = utcnow()
        release = f"{namespace}-{chart.name}"
        exec_result = self._helm.upgrade_install_from_repo(
            release_name=release,
            namespace=namespace,
            chart=chart,
            values=values,
            install_timeout_sec=install_timeout,
        )
        tests_timeout = service_chart.service_config.get("tests_timeout_sec")
        if not self._skip_tests and tests_enabled:
            test_result = self._helm.test_release(chart.path, release, namespace, timeout_sec=tests_timeout)  # type: ignore[arg-type]
        else:
            test_result = TestsResult.SKIPPED
        dry_run_str = "[dry run]" if self._dry_run else ""
        _logger.info(
            f"Installed {chart.name}/v{version} on {self._helm.cluster_name}/{namespace} tests: {test_result.value} time took: {exec_result.latency.total_seconds()} {dry_run_str}"
        )
        result = ServiceDeployResult(
            service_name=service_chart.service_name,
            revision=version,
            success=exec_result.success,
            tests=test_result,
            install_latency=exec_result.latency,
            deploy_time=deploy_time,
            output=exec_result.output,
            changes=tuple(),  # Doing it in dev first. will update in the future.
        )
        return result


class InstallServiceProdTool(ToolchainBinary):
    description = "Install service chart to our production Kubernetes cluster."
    _EMOJI = "kubernetes"

    def __init__(self, cmdline_args: Namespace) -> None:
        super().__init__(cmdline_args)
        self._services = extrapolate_services(cmdline_args.services)
        cluster = get_cluster(self._services)
        if cmdline_args.edge and cmdline_args.staging:
            raise ToolchainAssertion("--edge and --staging conflict and can not be passed in the same run.")
        self._installer = InstallServiceProd(
            aws_region=cmdline_args.aws_region,
            dry_run=cmdline_args.dry_run,
            namespace=get_namespace_for_cmd_args(cmdline_args),
            silent=cmdline_args.silent,
            cluster=cluster,
            emoji=self._EMOJI,
            keep_helm_files=cmdline_args.keep_helm_files,
            skip_tests=cmdline_args.skip_tests,
        )
        self._ignore_git_check = cmdline_args.ignore_git_check
        self._change_helper = ChangeHelper.create(cmdline_args.aws_region)
        self._notes: list[str] = []

    def run(self) -> int:
        if not self._check_git_state():
            return -1
        self._installer.install_services(services=self._services, notes=self._notes)
        return 0

    def _check_git_state(self) -> bool:
        if self._change_helper.check_git_state():
            return True
        if not self._ignore_git_check:
            return False
        self._notes.append(get_git_skip_note())
        return True

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        parser.add_argument("services", nargs="+", help="name of service(s) (infosite/infosite, buildsense/api, etc..)")
        cls.add_aws_region_argument(parser)
        parser.add_argument("--dry-run", action="store_true", required=False, default=False, help="Dry run")
        parser.add_argument(
            "--keep-helm-files", action="store_true", required=False, default=False, help="Preserve Helm values file"
        )
        parser.add_argument(
            "--staging", action="store_true", required=False, default=False, help="Deploy to staging environment"
        )
        parser.add_argument(
            "--edge", action="store_true", required=False, default=False, help="Deploy to edge environment"
        )
        parser.add_argument(
            "--silent",
            action="store_true",
            required=False,
            default=False,
            help="Send chat (Slack) messages to bots. Only allowed in staging.",
        )
        parser.add_argument(
            "--skip-tests",
            action="store_true",
            required=False,
            default=False,
            help="Skip running helm tests on installed services",
        )
        parser.add_argument(
            "--ignore-git-check",
            action="store_true",
            required=False,
            default=False,
            help=(
                "Continues even if there are local changes or the current branch is not latest "
                "master. This is not safe and should only be used in emergencies."
            ),
        )


if __name__ == "__main__":
    InstallServiceProdTool.start()
