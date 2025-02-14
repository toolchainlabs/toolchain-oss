#!/usr/bin/env ./python
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
from argparse import ArgumentParser, Namespace

from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.prod.aws_cost_reporter.calculate_cost import get_cost_report
from toolchain.util.logging.config_helpers import configure_for_tool
from toolchain.util.prod.chat_client import ChatClient
from toolchain.util.secret.secrets_accessor import KubernetesVolumeSecretsReader

_logger = logging.getLogger(__name__)


class AWSCostNotifierTool(ToolchainBinary):
    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._aws_region = cmd_args.aws_region
        reader = KubernetesVolumeSecretsReader()
        slack_webhook = reader.get_secret_or_raise("slack-webhook")
        self._chat = ChatClient.for_job(job_name="AWS Daily Costs", webhook_url=slack_webhook)

    def run(self) -> int:
        report = get_cost_report(self._aws_region, num_of_rows=7)
        message = report.to_message()
        _logger.info(message)
        self._chat.post_message(message=message, channel=ChatClient.Channel.DEVOPS)
        return 0

    @classmethod
    def configure_logging(cls, log_level, use_colors=True) -> None:
        configure_for_tool(log_level)

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)


if __name__ == "__main__":
    AWSCostNotifierTool.start()
