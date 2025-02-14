# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from requests_aws4auth import AWS4Auth

from toolchain.aws.aws_api import AWSService


def get_auth_for_service(aws_service: str, *, region_name: str | None = None):
    region_name = region_name or AWSService.get_default_region()
    credentials = AWSService.get_credentials()
    return AWS4Auth(
        credentials.access_key, credentials.secret_key, region_name, aws_service, session_token=credentials.token
    )
