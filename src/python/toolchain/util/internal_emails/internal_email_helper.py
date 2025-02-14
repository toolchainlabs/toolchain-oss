# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from toolchain.aws.ses import SES
from toolchain.base.toolchain_error import ToolchainAssertion


class SendEmailHelper:
    def __init__(self, templates_path: Path, aws_region: str | None = None) -> None:
        loader = FileSystemLoader(templates_path.as_posix())
        self._jinja_env = Environment(loader=loader, autoescape=select_autoescape(["html"]))
        self._ses = SES(aws_region)

    def send_email(self, email_address: str, subject: str, template_name: str, context: dict):
        if not email_address.lower().endswith("@toolchain.com"):
            raise ToolchainAssertion(
                "This tool should only be used to send emails to toolchain employees. not to customers/users."
            )
        template = self._jinja_env.get_template(template_name)
        html_content = template.render(context)
        self._ses.send_html_email(
            from_email="devinfra@toolchain.com",
            to_emails=[email_address],
            subject=subject,
            html_content=html_content,
        )
