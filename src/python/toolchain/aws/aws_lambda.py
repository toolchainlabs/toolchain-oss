# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import datetime
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass

from dateutil.parser import parse

from toolchain.aws.aws_api import AWSService
from toolchain.base.toolchain_error import ToolchainAssertion

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LambdaFunction:
    function_name: str
    revision_id: str
    last_modified: datetime.datetime
    version: str
    code_sha256: str


class Lambda(AWSService):
    service = "lambda"

    def invoke(self, function_name: str, version: str, payload: dict) -> str:
        response = self.client.invoke(
            FunctionName=function_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload).encode(),
            Qualifier=version,
        )
        # response payload is somehow a json string.
        return json.loads(response["Payload"].read())

    def update_function(self, *, function_name: str, s3_bucket: str, s3_key: str) -> LambdaFunction:
        response = self.client.update_function_code(
            FunctionName=function_name,
            S3Bucket=s3_bucket,
            S3Key=s3_key,
            Publish=False,
            DryRun=False,
        )
        return self._to_lambda_function(response)

    def publish_function(self, function_name: str, revision_id: str) -> LambdaFunction:
        response = self.client.publish_version(FunctionName=function_name, RevisionId=revision_id)
        return self._to_lambda_function(response)

    @classmethod
    def _to_lambda_function(cls, version_dict: dict) -> LambdaFunction:
        return LambdaFunction(
            function_name=version_dict["FunctionName"],
            revision_id=version_dict["RevisionId"],
            version=version_dict["Version"],
            last_modified=parse(version_dict["LastModified"]),
            code_sha256=version_dict["CodeSha256"],
        )

    def get_function(self, function_name: str, version: str) -> LambdaFunction:
        response = self.client.get_function(FunctionName=function_name, Qualifier=version)
        return self._to_lambda_function(response["Configuration"])

    def get_function_versions(self, function_name: str) -> tuple[LambdaFunction, ...]:
        response = self.client.list_versions_by_function(FunctionName=function_name)
        return tuple(self._to_lambda_function(vers_dict) for vers_dict in response["Versions"])

    def delete_function_versions(self, function_name: str, versions: Sequence[str]) -> None:
        for version in versions:
            if not version:
                raise ToolchainAssertion(f"Invalid version {version} for function: {function_name}")
            self.client.delete_function(FunctionName=function_name, Qualifier=version)
            _logger.info(f"deleted version {version} for {function_name}")
