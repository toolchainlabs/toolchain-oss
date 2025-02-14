#!/usr/bin/env ./python
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
from argparse import ArgumentParser, Namespace

from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.config.services import extrapolate_services
from toolchain.prod.builders.image_builder import build_services

_logger = logging.getLogger(__name__)


class BuildLocalServiceImage(ToolchainBinary):
    """Build a local service image without performing any deploy-related actions."""

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._services = extrapolate_services(cmd_args.services)
        self._workers = cmd_args.workers

    def run(self) -> int:
        services_str = ", ".join(service.service_name for service in self._services)
        _logger.info(f"Building: {services_str}")
        build_results = build_services(self._services, env_name="local", max_workers=self._workers, push=False)
        for build_result in build_results:
            _logger.info(f"Built {build_result.service.service_name}")
        return 0

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        super().add_arguments(parser)
        parser.add_argument("services", nargs="+")
        parser.add_argument(
            "--workers", required=False, type=int, default=None, help="Number of parallel docker image builders"
        )


if __name__ == "__main__":
    BuildLocalServiceImage.start()
