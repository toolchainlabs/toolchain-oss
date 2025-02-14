#!/usr/bin/env ./python
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime
import logging
from argparse import ArgumentParser, Namespace

from toolchain.aws.aws_lambda import Lambda
from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.prod.installs.install_buildsense_lambda import InstallBuildsenseLambda

_logger = logging.getLogger(__name__)


class PurgeBuildsenseLambdaVersions(ToolchainBinary):
    _MIN_VERSIONS = 5
    # Updates to the lambda functions are rare (only when changing RunInfo) so 6mo is a sane value at this time.
    _MIN_MODIFIED_AGE = utcnow() - datetime.timedelta(days=180)

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        _logger.info(f"PurgeBuildsenseLambdaVersions arguments: {cmd_args}")
        self._func_name = InstallBuildsenseLambda.get_function_name(is_prod=cmd_args.prod)
        self._aws_lambda = Lambda(cmd_args.aws_region)
        self._skip_age_filter = cmd_args.skip_age_filter
        self._dry_run = not cmd_args.no_dry_run

    def run(self) -> int:
        versions = self._aws_lambda.get_function_versions(self._func_name)
        if len(versions) < self._MIN_VERSIONS:
            _logger.warning(
                f"less than {self._MIN_VERSIONS} for function: {self._func_name} ({len(versions)}) - not purging"
            )
            return -1

        functions_to_delete = sorted(versions, key=lambda ver: ver.last_modified)
        if not self._skip_age_filter:
            functions_to_delete = [ver for ver in functions_to_delete if ver.last_modified < self._MIN_MODIFIED_AGE]
        functions_to_delete = functions_to_delete[: -self._MIN_VERSIONS]
        _logger.info(
            f"Deleting {len(functions_to_delete)} out of {len(versions)} versions for {self._func_name}. dry_run={self._dry_run}"
        )
        _logger.info("\n".join(f"version: {v.version}: {v.last_modified}" for v in functions_to_delete))
        versions_ids = [fv.version for fv in functions_to_delete]
        if not self._dry_run:
            self._aws_lambda.delete_function_versions(function_name=self._func_name, versions=versions_ids)
        return 0

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)
        parser.add_argument(
            "--prod",
            action="store_true",
            required=False,
            default=False,
            help="Purge function in prod environment (defaults to dev).",
        )
        parser.add_argument(
            "--skip-age-filter",
            action="store_true",
            required=False,
            default=False,
            help="Skip minimal age check when deleting function versions.",
        )
        parser.add_argument("--no-dry-run", action="store_true", required=False, default=False, help="Disable dry run.")


if __name__ == "__main__":
    PurgeBuildsenseLambdaVersions.start()
