# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

from toolchain.aws.aws_api import AWSService
from toolchain.base.email import parse_email
from toolchain.base.toolchain_error import ToolchainAssertion

_logger = logging.getLogger(__name__)
_ALLOWED_EMAIL_DOMAIN = "toolchain.com"


class SES(AWSService):
    service = "ses"

    def send_html_email(self, *, from_email: str, to_emails: list[str], subject: str, html_content: str) -> str:
        _, domain = parse_email(from_email.lower())
        if domain != _ALLOWED_EMAIL_DOMAIN:
            raise ToolchainAssertion(f"from email must be in @{_ALLOWED_EMAIL_DOMAIN}")
        msg_dict = {"Subject": {"Data": subject}, "Body": {"Html": {"Data": html_content}}}
        emails_str = ", ".join(to_emails)
        _logger.info(f"Sending email to: {emails_str} with subject: {subject}")
        response = self.client.send_email(Source=from_email, Destination={"ToAddresses": to_emails}, Message=msg_dict)
        return response["MessageId"]

    def send_raw_email(self, from_email: str, to_emails: list[str], message: bytes) -> str:
        emails_str = ", ".join(to_emails)
        _logger.info(f"Sending raw email to: {emails_str}")
        response = self.client.send_raw_email(Source=from_email, Destinations=to_emails, RawMessage={"Data": message})
        return response["MessageId"]
