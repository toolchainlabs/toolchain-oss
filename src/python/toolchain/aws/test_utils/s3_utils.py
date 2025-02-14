# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import boto3

from toolchain.aws.test_utils.common import TEST_REGION


def create_s3_bucket(bucket_name: str, region: str = TEST_REGION):
    conn = boto3.resource("s3", region_name=region)
    conn.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={"LocationConstraint": region})


def assert_bucket_empty(s3, bucket_name: str, key_prefix: str | None = None) -> None:
    keys = s3.keys_with_prefix(bucket=bucket_name, key_prefix=key_prefix or "")
    assert next(keys, None) is None
