#!/usr/bin/env ./python
# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json
import logging
from argparse import ArgumentParser, Namespace

from toolchain.aws.s3 import S3
from toolchain.base.toolchain_binary import ToolchainBinary

_logger = logging.getLogger(__name__)


class GetReferrals(ToolchainBinary):
    _BUCKET = "scm-integration.us-east-1.toolchain.com"
    # pantsbuild org & pants build repo IDs in prod
    _PATH = "prod/v1/github/statistics/exBgciGKk7hyzGVQ7MDsTn/GJCKewAj98kACMyCTPnCE9"
    _FILE = "repo_referral_sources.json"

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        self._s3 = S3(cmd_args.aws_region)

    def run(self) -> int:
        domains: set[str] = set()
        for key in self._s3.keys_with_prefix(bucket=self._BUCKET, key_prefix=self._PATH):
            if not key.endswith(self._FILE):
                continue
            data = self._s3.get_content(self._BUCKET, key)
            domains.update(node["referrer"] for node in json.loads(data))
        referrers = sorted(domains)
        _logger.info(f"Referrers: {referrers}")
        return 0

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)


if __name__ == "__main__":
    GetReferrals.start()
