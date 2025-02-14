#!/usr/bin/env ./python
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
from argparse import ArgumentParser, Namespace
from collections.abc import Sequence

from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.config.services import ServicesBuildResults, ToolchainService, extrapolate_services
from toolchain.prod.builders.e2e_tests_builder import End2EndTestBuilder
from toolchain.prod.builders.image_builder import build_services
from toolchain.prod.installs.install_service_dev import InstallServiceDev
from toolchain.util.net.net_util import get_remote_username

_logger = logging.getLogger(__name__)


class BuildAndDeployServiceDev(ToolchainBinary):
    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._services = extrapolate_services(cmd_args.services)
        self._namespaces = sorted(cmd_args.namespaces or [get_remote_username()])
        self._delete_services = cmd_args.delete
        self._workers = cmd_args.workers
        self._installer = InstallServiceDev(
            aws_region=cmd_args.aws_region,
            dry_run=cmd_args.dry_run,
            keep_helm_files=cmd_args.keep_helm_files,
            skip_tests=cmd_args.skip_tests,
        )

    def run(self) -> int:
        services = self._services
        services_str = ", ".join(tup.service_name for tup in services)
        ns_str = ", ".join(self._namespaces)
        _logger.info(f"Installing: {services_str} to namespaces: {ns_str}")
        env_name = f"dev-{self._namespaces[0]}"
        build_results = build_services(services, env_name=env_name, max_workers=self._workers)
        self._build_and_attach_tests(env_name, services, build_results)
        self._installer.install_services(self._namespaces, build_results, delete_first=self._delete_services)
        return 0

    def _build_and_attach_tests(
        self, env_name, services: Sequence[ToolchainService], build_results: ServicesBuildResults
    ) -> None:
        test_builder = End2EndTestBuilder(env_name)
        tests_images = test_builder.build_tests(services)
        for build_result in build_results:
            build_result.tests_images = tests_images.get(build_result.service)

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        parser.add_argument("services", nargs="+")
        cls.add_aws_region_argument(parser)
        parser.add_argument("--namespaces", nargs="+", help="Kubernetes namespaces to install services to.")
        parser.add_argument("--dry-run", action="store_true", required=False, default=False, help="Do a dry run.")
        parser.add_argument(
            "--delete",
            action="store_true",
            required=False,
            default=False,
            help="Delete services before re-installing them.",
        )
        parser.add_argument(
            "--workers", required=False, type=int, default=None, help="Number of parallel docker image builders"
        )
        parser.add_argument(
            "--keep-helm-files",
            required=False,
            action="store_true",
            default=False,
            help="Do not erase temporary files passed to helm",
        )
        parser.add_argument(
            "--skip-tests",
            action="store_true",
            required=False,
            default=False,
            help="Skip running helm tests on installed services",
        )


if __name__ == "__main__":
    BuildAndDeployServiceDev.start()
