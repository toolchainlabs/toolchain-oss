# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, unique
from pathlib import Path
from typing import cast

from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.kubernetes.cluster import ClusterAPI
from toolchain.kubernetes.constants import KubernetesCluster
from toolchain.prod.tools.changes_helper import ChangeMessages
from toolchain.prod.tools.utils import Deployer
from toolchain.util.internal_emails.internal_email_helper import SendEmailHelper
from toolchain.util.prod.chat_client import Channel, ChatClient
from toolchain.util.prod.helm_charts import HelmChart
from toolchain.util.prod.helm_client import HelmExecuteResult, TestsResult

_logger = logging.getLogger(__name__)


@unique
class DeployType(Enum):
    SERVICES = "Services"
    CHART = "Charts"
    FRONTEND = "Frontend"


@dataclass(frozen=True)
class ServiceDeployResult:
    service_name: str
    revision: str
    success: bool
    output: str
    tests: TestsResult
    deploy_time: datetime.datetime
    install_latency: datetime.timedelta
    changes: ChangeMessages


@dataclass(frozen=True)
class ChartDeployResult:
    chart_name: str
    chart_version: str
    success: bool
    output: str
    deploy_time: datetime.datetime
    install_latency: datetime.timedelta
    namespace: str

    @classmethod
    def create(
        cls, chart: HelmChart, exec_result: HelmExecuteResult, deploy_time: datetime.datetime
    ) -> ChartDeployResult:
        return cls(
            chart_name=chart.name,
            chart_version=chart.version,
            deploy_time=deploy_time,
            output=exec_result.output,
            success=exec_result.success,
            install_latency=exec_result.latency,
            namespace=cast(str, exec_result.namespace),
        )

    @property
    def installed_chart(self) -> str:
        return f"{self.chart_name}-v{self.chart_version}"


@dataclass(frozen=True)
class DeployResult:
    deploy_type: DeployType
    dry_run: bool
    deployer: Deployer

    @property
    def name(self) -> str:
        return self.deploy_type.value

    @property
    def target(self) -> str:
        raise NotImplementedError("Subclass must implement target.")

    @property
    def namespaces(self) -> str:
        raise NotImplementedError("Subclass must implement namespaces.")

    def get_message(self):
        raise NotImplementedError("Subclass must implement get_message().")


@dataclass(frozen=True)
class KubernetesDeployResult(DeployResult):
    cluster: KubernetesCluster

    @property
    def target(self) -> str:
        return self.cluster.value


@dataclass(frozen=True)
class ChartDeployResults(KubernetesDeployResult):
    charts: tuple[ChartDeployResult, ...]
    extra_info: str | None = None

    @classmethod
    def for_multiple_charts(
        cls, cluster: KubernetesCluster, dry_run: bool, deployer: Deployer, *results: ChartDeployResult
    ) -> ChartDeployResults:
        return cls(deploy_type=DeployType.CHART, cluster=cluster, dry_run=dry_run, deployer=deployer, charts=results)

    @classmethod
    def create(
        cls,
        *,
        deployer: Deployer,
        chart: HelmChart,
        deploy_time: datetime.datetime,
        exec_result: HelmExecuteResult,
        extra_info: str | None = None,
    ) -> ChartDeployResults:
        chart_deploy = ChartDeployResult.create(chart, exec_result, deploy_time)
        return cls(
            deploy_type=DeployType.CHART,
            cluster=exec_result.cluster,
            dry_run=exec_result.dry_run,
            deployer=deployer,
            extra_info=extra_info,
            charts=(chart_deploy,),
        )

    def _get_namespaces(self) -> tuple[str, ...]:
        return tuple({chart.namespace for chart in self.charts})

    @property
    def namespaces(self) -> str:
        return ",".join(self._get_namespaces())

    def get_message(self) -> str:
        namespaces = self._get_namespaces()
        if len(namespaces) == 1:
            charts = ", ".join(chart.installed_chart for chart in self.charts)
            message = f"Installed {charts} into {self.target}/{namespaces[0]}"
        else:
            charts = ", ".join(f"{chart.installed_chart}/{chart.namespace}" for chart in self.charts)
            message = f"Installed {charts} into {self.target}"
        if self.extra_info:
            message = f"{message} {self.extra_info}"
        return message


@dataclass(frozen=True)
class ServicesDeployResult(KubernetesDeployResult):
    namespace: str
    services: tuple[ServiceDeployResult, ...]
    notes: str

    @classmethod
    def create(
        cls,
        *,
        deployer: Deployer,
        cluster: KubernetesCluster,
        namespace: str,
        dry_run: bool,
        services: Sequence[ServiceDeployResult],
        notes: Sequence[str] | None = None,
    ) -> ServicesDeployResult:
        return cls(
            deploy_type=DeployType.SERVICES,
            cluster=cluster,
            namespace=namespace,
            dry_run=dry_run,
            services=tuple(services),
            deployer=deployer,
            notes="\n".join(notes or []),
        )

    @property
    def count(self) -> int:
        return len(self.services)

    @property
    def namespaces(self) -> str:
        return self.namespace

    def get_message(self) -> str:
        service_list = ", ".join(result.service_name for result in self.services)
        notes = f"\n{self.notes}" if self.notes else ""
        return f"Installed {service_list} service(s) chart to {self.target}/{self.namespace}.{notes}"


@dataclass(frozen=True)
class FrontendDeployResult(KubernetesDeployResult):
    namespace: str
    version: str
    domain: str
    manifest_key: str
    bucket: str
    changes: ChangeMessages
    app: str

    @property
    def namespaces(self) -> str:
        return self.namespace

    def get_message(self) -> str:
        return f"Deployed {self.app} version {self.version} to {self.namespace}/{self.target}."


class DeployNotifications:
    _NOTIFY_EMAIL_ANNOTATION = "toolchain.deploy-notification/email"
    _PROD_DEPLOY_EMAIL = "ops-notify@toolchain.com"
    _TEMPLATES_MAP = {
        DeployType.SERVICES: "deploy_services_email.html",
        DeployType.CHART: "deploy_chart_email.html",
        DeployType.FRONTEND: "deploy_frontend_email.html",
    }

    def __init__(self, is_prod: bool, aws_region: str, user: str) -> None:
        self._is_prod = is_prod
        self._aws_region = aws_region
        self._chat = ChatClient.for_devops(aws_region=self._aws_region, user=user) if is_prod else None

    def notify_deploy(
        self,
        deploy_result: DeployResult,
        quiet: bool = False,
        channel: Channel | None = None,
        emoji: str | None = None,
    ):
        if self._is_prod:
            self._notify_chat_prod(deploy_result, quiet, channel, emoji)
            self._email_deploy(self._PROD_DEPLOY_EMAIL, deploy_result)
        else:
            if not isinstance(deploy_result, KubernetesDeployResult):
                raise ToolchainAssertion(f"Unexpected dev deploy result: {deploy_result}")
            self.notify_deploy_to_dev(deploy_result)

    def _notify_chat_prod(self, deploy_results: DeployResult, quiet: bool, channel: Channel | None, emoji: str | None):
        msg = deploy_results.get_message()
        default_channel = Channel.BOTS if quiet else Channel.DEVOPS
        if deploy_results.dry_run:
            msg += " [dry run]"
        self._chat.post_message(  # type: ignore[union-attr]
            msg, serverity=ChatClient.Severity.INFO, channel=channel or default_channel, emoji=emoji
        )

    def _email_deploy(self, email_address: str | None, deploy_result: DeployResult):
        namespaces = deploy_result.namespaces
        if not email_address:
            _logger.warning(f"No email annotation for namespace: {namespaces}")
            return
        email_helper = SendEmailHelper(templates_path=Path(__file__).parent / "templates", aws_region=self._aws_region)
        deploy_target = f"{deploy_result.target}/{namespaces}"
        _logger.info(f"Notify {deploy_result.name.lower()} deploy to {deploy_target}.")
        email_helper.send_email(
            email_address=email_address,
            subject=f"{deploy_result.name} deployed to {deploy_target}",
            template_name=self._TEMPLATES_MAP[deploy_result.deploy_type],
            context={
                "deploy_target": deploy_target,
                "namespace": namespaces,
                "deployer": deploy_result.deployer.formatted_deployer,
                "deploy_result": deploy_result,
            },
        )

    def notify_deploy_to_dev(self, deploy_result: KubernetesDeployResult):
        cluster = ClusterAPI.for_cluster(deploy_result.cluster)
        email_address = cluster.get_namespace_annotation(
            namespace=deploy_result.namespaces, annotation=self._NOTIFY_EMAIL_ANNOTATION
        )
        self._email_deploy(email_address, deploy_result)


def notify_devops_chart_deploy(
    *,
    chart: HelmChart,
    exec_result: HelmExecuteResult,
    deployer: Deployer,
    deploy_time: datetime.datetime,
    aws_region: str,
    emoji: str,
    silent: bool = False,
    is_prod: bool = True,
    extra_info: str | None = None,
) -> None:
    chat_channel = ChatClient.Channel.ALERTS if silent else ChatClient.Channel.DEVOPS
    deploy_result = ChartDeployResults.create(
        deployer=deployer,
        chart=chart,
        deploy_time=deploy_time,
        exec_result=exec_result,
        extra_info=extra_info,
    )
    notifications = DeployNotifications(is_prod=is_prod, aws_region=aws_region, user=deployer.formatted_deployer)
    notifications.notify_deploy(deploy_result=deploy_result, quiet=False, channel=chat_channel, emoji=emoji)
