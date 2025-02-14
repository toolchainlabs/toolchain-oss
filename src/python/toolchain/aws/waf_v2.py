# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import logging

from toolchain.aws.aws_api import AWSService
from toolchain.base.toolchain_error import ToolchainAssertion

_logger = logging.getLogger(__name__)


class WAF(AWSService):
    service = "wafv2"

    def get_web_acl_arn(self, name: str) -> str:
        response = self.client.list_web_acls(Scope="REGIONAL")
        if "NextMarker" in response:
            # not supporting pagination yet.
            raise NotImplementedError
        for web_acl in response["WebACLs"]:
            if web_acl["Name"] == name:
                return web_acl["ARN"]
        raise ToolchainAssertion(f"No WAF Web Acl named '{name}' found")
