#!/usr/bin/env ./python
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging
from argparse import ArgumentParser, Namespace
from collections.abc import Sequence

from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.config.services import ServiceBuildResult, ServicesBuildResults, ToolchainService, extrapolate_services
from toolchain.kubernetes.constants import KubernetesCluster
from toolchain.prod.builders.e2e_tests_builder import End2EndTestBuilder
from toolchain.prod.builders.image_builder import build_services
from toolchain.prod.installs.install_service_prod import InstallServiceProd, get_git_skip_note
from toolchain.prod.tools.changes_helper import ChangeHelper, ServicesVersions
from toolchain.prod.tools.utils import get_cluster, get_namespace_for_cmd_args
from toolchain.util.prod.helm_charts import HelmChart, ServiceChartInfo

_logger = logging.getLogger(__name__)


class BuildAndDeployServicesProd(ToolchainBinary):
    _EMOJI = "python"
    _ENV_NAME = "prod"

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._services = extrapolate_services(cmd_args.services)
        if not self._services:
            raise ToolchainAssertion(f"No services extrapolated for '{cmd_args.services}'")
        cluster = get_cluster(self._services)
        self._workers = cmd_args.workers
        self._ignore_git_check = cmd_args.ignore_git_check
        self._aws_region = cmd_args.aws_region
        self._skip_migrations_check = (
            KubernetesCluster(cluster) == KubernetesCluster.REMOTING or cmd_args.skip_migrations
        )
        self._change_helper = ChangeHelper.create(cmd_args.aws_region)
        self._skip_tests = cmd_args.skip_tests
        self._installer = InstallServiceProd(
            aws_region=cmd_args.aws_region,
            dry_run=cmd_args.dry_run,
            namespace=get_namespace_for_cmd_args(cmd_args),
            silent=cmd_args.silent,
            cluster=cluster,
            emoji=self._EMOJI,
            skip_tests=cmd_args.skip_tests,
        )
        self._notes: list[str] = []

    def _check_git_state(self) -> bool:
        if self._change_helper.check_git_state():
            return True
        if not self._ignore_git_check:
            return False
        self._notes.append(get_git_skip_note())
        return True

    def run(self) -> int:
        services = self._services
        if not self._check_git_state():
            return -1

        build_results = build_services(services, env_name=self._ENV_NAME, max_workers=self._workers)
        self._build_and_attach_tests(services, build_results)
        if not self._check_git_state():
            return -1
        chart_versions = self._update_charts(build_results)
        if not self._skip_migrations_check:
            migrations_ok = self._change_helper.check_pending_migrations(chart_versions)
            if not migrations_ok:
                return -1
        self._installer.install_services([build_result.service for build_result in build_results], notes=self._notes)
        return 0

    def _build_and_attach_tests(
        self, services: Sequence[ToolchainService], build_results: ServicesBuildResults
    ) -> None:
        if self._skip_tests:
            return
        test_builder = End2EndTestBuilder(self._ENV_NAME)
        tests_images = test_builder.build_tests(services)
        for build_result in build_results:
            build_result.tests_images = tests_images.get(build_result.service)

    def _update_service_images_revisions(
        self, chart: HelmChart, values: dict, build_result: ServiceBuildResult
    ) -> dict:
        versions_changes = {}
        for chart_parameter in build_result.chart_parameters:
            old_image_tag = values[chart_parameter][self._aws_region]
            values[chart_parameter][self._aws_region] = build_result.revision

            if old_image_tag:
                *_, old_revision = old_image_tag.rpartition("-")
                versions_changes[build_result.service.name] = (old_revision, build_result.commit_sha)
        chart.save_values(values)
        return versions_changes

    def _update_e2e_test_images_revisions(
        self, chart: HelmChart, values: dict, build_result: ServiceBuildResult
    ) -> None:
        if not build_result.tests_images:
            return
        e2e_test_values = values["tests"]
        if len(build_result.tests_images) > 1:
            # Need a way to set version for multiple images. will do that later on.
            raise ToolchainAssertion("More than one test image is currently unsupported.")
        for test_name, test_img_revision in build_result.tests_images.items():
            e2e_test_values[test_name]["image_rev"][self._aws_region] = test_img_revision
        chart.save_values(values)

    def _update_charts(self, build_results: ServicesBuildResults) -> ServicesVersions:
        versions_changes = {}
        for build_result in build_results:
            chart = ServiceChartInfo.for_service(build_result.service)
            chart = HelmChart.for_path(chart.chart_path)
            values = chart.get_values(with_roundtrip=True)
            svc_versions_changes = self._update_service_images_revisions(chart, values, build_result)
            versions_changes.update(svc_versions_changes)
            self._update_e2e_test_images_revisions(chart, values, build_result)
        return versions_changes

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        parser.add_argument("services", nargs="+")
        cls.add_aws_region_argument(parser)
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
        parser.add_argument("--dry-run", action="store_true", required=False, default=False, help="Dry run")
        parser.add_argument(
            "--prod", action="store_true", required=False, default=False, help="Deploy to prod namespace"
        )
        parser.add_argument(
            "--edge", action="store_true", required=False, default=False, help="Deploy to edge namespace"
        )
        parser.add_argument(
            "--workers", required=False, type=int, default=None, help="Number of parallel docker image builders"
        )
        parser.add_argument(
            "--silent",
            action="store_true",
            required=False,
            default=False,
            help="Send chat (Slack) messages to bots. Only allowed in staging.",
        )
        parser.add_argument(
            "--skip-migrations",
            action="store_true",
            required=False,
            default=False,
            help="Skip making a migrations checks",
        )
        parser.add_argument(
            "--skip-tests",
            action="store_true",
            required=False,
            default=False,
            help="Skip running helm tests on installed services",
        )


if __name__ == "__main__":
    BuildAndDeployServicesProd.start()
