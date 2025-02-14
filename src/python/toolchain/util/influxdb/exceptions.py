# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import json

from influxdb_client.rest import ApiException

from toolchain.base.toolchain_error import ToolchainError


class MissingBucketError(ToolchainError):
    @classmethod
    def from_api_error(cls, api_error: ApiException) -> MissingBucketError:
        message = json.loads(api_error.body)["message"]
        return cls(message)


def is_missing_bucket_error(api_error: ApiException) -> bool:
    return api_error.status == 404 and "application/json" in api_error.headers.get("Content-Type", "")
