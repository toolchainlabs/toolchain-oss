#!/usr/bin/env ./python
# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import logging
import textwrap
from argparse import ArgumentParser, Namespace

from toolchain.aws.iam import IAM
from toolchain.aws.ses import SES
from toolchain.base.datetime_tools import utcnow
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.util.logging.config_helpers import configure_for_tool

_logger = logging.getLogger(__name__)

_EMAILS_TAG = "notify_emails"
_EMAIL_DOMAIN = "toolchain.com"
_SENDER = "ops@toolchain.com"


class IAMAccessKeysWatcher(ToolchainBinary):
    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._aws_region = cmd_args.aws_region
        self._notify_age = datetime.timedelta(days=cmd_args.notify_days)
        self._delete_age = datetime.timedelta(days=cmd_args.delete_days)
        _logger.info(
            f"IAMAccessKeysWatcher: delete_age={self._delete_age} notify_age={self._notify_age} aws_region={self._aws_region}"
        )
        self._iam = IAM(self._aws_region)
        self._ses = SES(self._aws_region)

    def run(self) -> int:
        self.check_iam_creds(notify_age=self._notify_age, delete_age=self._delete_age)
        return 0

    def check_iam_creds(self, notify_age: datetime.timedelta, delete_age: datetime.timedelta) -> tuple[int, int]:
        if notify_age >= delete_age:
            raise ToolchainAssertion(f"Notify value {notify_age} must be lower than deactivation value {delete_age}")
        now = utcnow()
        notify_threshold = now - notify_age
        delete_threshold = now - delete_age
        users = self._iam.get_users_with_old_keys(notify_threshold)
        deleted = 0
        if not users:
            _logger.info(f"No users w/ keys created before: {notify_threshold.isoformat()}")
        for user in users:
            to_emails = user.tags.get(_EMAILS_TAG, f"{user.name}@{_EMAIL_DOMAIN}").split(" ")
            should_delete = user.key_date < delete_threshold
            if should_delete:
                deleted += 1
                self._iam.delete_access_key(user)
                subject = f"Keys deleted for IAM User {user.name}."
                message = f"IAM Access keys have been deleted for {user.name} since they are over the allowed age ({delete_age.days} days)."
            else:
                _logger.info(f"Notify user {user.name} - {to_emails}")
                subject = f"IAM User {user.name} has old access keys."
                message = textwrap.dedent(
                    f"""
                Please generate a new AWS IAM Access key.
                You can run `./pants run src/python/toolchain/prod/aws_creds:rotate-aws-creds` to rotate your access key.
                <br/><br/>
                (Keys will be automatically deleted if they are older than {delete_age.days} days on {(user.key_date+delete_age).date().isoformat()}.)
                """
                )
            self._ses.send_html_email(from_email=_SENDER, to_emails=to_emails, subject=subject, html_content=message)
        return len(users), deleted

    @classmethod
    def configure_logging(cls, log_level, use_colors=True) -> None:
        configure_for_tool(log_level)

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)
        parser.add_argument(
            "--notify-days", type=int, metavar="int", required=False, default=110, help="Number of days "
        )
        parser.add_argument(
            "--delete-days", type=int, metavar="int", required=False, default=900, help="Number of days "
        )


if __name__ == "__main__":
    IAMAccessKeysWatcher.start()
