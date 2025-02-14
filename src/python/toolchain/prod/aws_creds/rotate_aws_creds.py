#!/usr/bin/env ./python
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
import os
from argparse import ArgumentParser, Namespace
from pathlib import Path

from toolchain.aws.aws_api import AWSService
from toolchain.aws.iam import IAM, IAMAccessKey
from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.base.toolchain_error import ToolchainAssertion

logger = logging.getLogger(__name__)


class RotateAWSCreds(ToolchainBinary):
    """Rotate a Toolchain employee's AWS credentials."""

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._aws_region = cmd_args.aws_region
        self._deactivate_access_key = cmd_args.deactivate_access_key
        self._iam = IAM(region=self._aws_region)

    def _rewrite_creds(
        self, creds_contents: str, old_access_key_id: str, old_secret_access_key: str, new_access_key: IAMAccessKey
    ) -> str:
        new_creds_contents = creds_contents.replace(old_access_key_id, new_access_key.access_key_id)
        new_creds_contents = new_creds_contents.replace(old_secret_access_key, new_access_key.secret_access_key)
        return new_creds_contents

    def run(self) -> int:
        creds_path = Path.home() / ".aws" / "credentials"
        if not creds_path.exists():
            raise ToolchainAssertion(f"AWS credentials file does not exist: {creds_path}")

        old_creds_contents = creds_path.read_text()

        credentials = AWSService.get_credentials()
        if credentials.access_key not in old_creds_contents or credentials.secret_key not in old_creds_contents:
            raise ToolchainAssertion("This script requires the existing AWS credentials to be in ~/.aws/credentials.")

        user_name = self._iam.get_current_user_name()
        logger.info(f"Rotating AWS credentials for user {user_name}.")

        deleted_count = self._iam.delete_inactive_keys(user_name)
        logger.info(f"Deleted {deleted_count} inactive keys.")

        new_access_key = self._iam.create_access_key(user_name)
        logger.info(f"Created new access key for user {user_name} with ID {new_access_key.access_key_id}.")

        new_creds_contents = self._rewrite_creds(
            old_creds_contents, credentials.access_key, credentials.secret_key, new_access_key
        )

        # Rename the existing credentials file to a new name for safety and then write the modified file.
        renamed_creds_path = creds_path.with_name(f"{creds_path.name}-{utcnow().strftime('%Y%m%d%H%M%S')}")
        creds_path.replace(renamed_creds_path)
        logger.info(f"Renamed {creds_path} to {renamed_creds_path}.")

        # This is a little elaborate, but is the only robust way to write a file that without it
        # being world-readable for at least a short window (and if this script crashes in that
        # window the creds will remain world-readable).
        with open(os.open(creds_path, os.O_TRUNC | os.O_WRONLY | os.O_CREAT, 0o400), "w") as fh:
            fh.write(new_creds_contents)
        logger.info(f"Updated {creds_path} with new access key and secret.")

        # Delete the previous access key.
        if self._deactivate_access_key:
            self._iam.deactivate_access_key(user_name, credentials.access_key)
            logger.info(f"Deactivated previous access key with ID {credentials.access_key}.")

        return 0

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)
        parser.add_argument(
            "--no-deactivate-access-key",
            dest="deactivate_access_key",
            action="store_false",
            default=True,
            help="Do not deactivate the old access key",
        )


if __name__ == "__main__":
    RotateAWSCreds.start()
