#!/usr/bin/env ./python
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
from argparse import ArgumentParser, Namespace

from toolchain.aws.ecr import ECR
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.config.services import get_service

logger = logging.getLogger(__name__)


class EnsureEcrRepo(ToolchainBinary):
    description = "Ensure that a service's ECR repo exists in the given region."

    @classmethod
    def run_for_service(cls, aws_region: str, service: str, dry_run: bool) -> None:
        tool = cls.create_for_args(aws_region=aws_region, service=service, dry_run=dry_run)
        tool.run()

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._aws_region = cmd_args.aws_region
        self._service = cmd_args.service
        self._dry_run = cmd_args.dry_run

    def run(self) -> int:
        ecr = ECR(region=self._aws_region)
        repo = get_service(self._service).ecr_repo_name
        if not repo:
            return -1
        if self._dry_run:
            logger.info(f"ECR repo [dry-run] {repo}")
            return 0
        created = ecr.ensure_repository(repo)
        logger.info(f"ECR repo {repo} {created=}")
        return 0

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)
        parser.add_argument("--service", metavar="name", required=True, help="The name of the service.")
        parser.add_argument("--dry-run", action="store_true", required=False, default=False, help="Dry run.")


if __name__ == "__main__":
    EnsureEcrRepo.start()
