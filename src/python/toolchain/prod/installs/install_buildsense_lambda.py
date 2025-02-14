#!/usr/bin/env ./python
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import json
import logging
from argparse import ArgumentParser, Namespace

from toolchain.aws.aws_lambda import Lambda
from toolchain.aws.s3 import S3
from toolchain.base.fileutil import safe_copy_file
from toolchain.base.toolchain_binary import ToolchainBinary
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.prod.tools.changes_helper import ChangeHelper
from toolchain.util.prod.git_tools import get_version_tag

_logger = logging.getLogger(__name__)


class InstallBuildsenseLambda(ToolchainBinary):
    _PROD_FUNCTION_NAME = "prod-buildsense-dynamodb-to-es"
    _DEV_FUNCTION_NAME = "dev-buildsense-dynamodb-to-es"
    _S3_BUCKET = "artifacts.{region}.toolchain.com"
    _S3_KEY_PREFIX = "{env}/v1/bin/awslambda/buildsense"
    MAX_VERSIONS = 25

    def __init__(self, cmd_args: Namespace) -> None:
        super().__init__(cmd_args)
        _logger.info(f"InstallBuildsenseLambda arguments: {cmd_args}")
        self._aws_region = cmd_args.aws_region
        self._is_prod = cmd_args.prod
        self._env = "prod" if cmd_args.prod else "dev"
        self._func_name = self.get_function_name(self._is_prod)
        self._bucket = self._S3_BUCKET.format(region=self._aws_region)
        self._key_prefix = self._S3_KEY_PREFIX.format(env=self._env)
        self._aws_lambda = Lambda(self._aws_region)

    @classmethod
    def get_function_name(cls, is_prod: bool) -> str:
        return cls._PROD_FUNCTION_NAME if is_prod else cls._DEV_FUNCTION_NAME

    def run(self) -> int:
        if self._is_prod and not ChangeHelper.check_git_state():
            return -1
        versions_count = len(self._aws_lambda.get_function_versions(function_name=self._func_name))
        _logger.info(f"function: {self._func_name} versions: {versions_count}")
        if versions_count >= self.MAX_VERSIONS:
            _logger.warning(
                f"Max number of versions for lambda function: {self._func_name}, to purge old versions run: './pants run src/python/toolchain/prod/installs:purge_old_buildsenese_lambda_versions'"
            )
            return -1
        s3 = S3(self._aws_region)
        func_zip_file = f"dynamodb-to-es-lambda-{get_version_tag()}.zip"
        local_file_path = f"dist/{func_zip_file}"
        safe_copy_file(
            "dist/src.python.toolchain.buildsense.dynamodb_es_bridge/dynamodb-to-es-lambda.zip", local_file_path
        )
        s3_key = f"{self._key_prefix}/{func_zip_file}"
        _logger.info(f"Upload {local_file_path} to s3://{self._bucket}/{s3_key}")
        s3.upload_file(bucket=self._bucket, key=s3_key, path=local_file_path, content_type="application/octet-stream")
        func = self._aws_lambda.update_function(function_name=self._func_name, s3_bucket=self._bucket, s3_key=s3_key)
        success = self._check_opensearch_connectivity(func.version)
        # for some unknown reason, the revision_id returned from the update function API can't be used w/ the publish_function API
        # so we have to call the get_function api in order to get the correct revision_id.
        # We have a safety check to make sure the function we will publish is the same one we updated (based on code sha256 and last_modified)
        updated_func = self._aws_lambda.get_function(function_name=self._func_name, version=func.version)
        _logger.info(
            f"Updated function {self._env}/{self._func_name} version: {func.version} revision: {func.revision_id} code sha256: {func.code_sha256}"
        )
        if func.last_modified != updated_func.last_modified or func.code_sha256 != updated_func.code_sha256:
            raise ToolchainAssertion(f"Unexpected function properties. {func=} {updated_func=}")
        if success:
            self._aws_lambda.publish_function(function_name=self._func_name, revision_id=updated_func.revision_id)
            _logger.info(
                f"Published function {self._env}/{self._func_name} version: {updated_func.version} revision: {updated_func.revision_id}"
            )
        return 0 if success else -1

    def _check_opensearch_connectivity(self, version: str) -> bool:
        response = self._aws_lambda.invoke(self._func_name, version=version, payload={"CHECKS": "ES"})
        if isinstance(response, dict):
            # If we get a response from ES, it will be a string. if something fails then the response
            # is json data (which invoke parses) from the AWS API that gives information about the failure.
            _logger.warning(response)
            return False
        es_response = json.loads(response)
        if es_response.get("tagline", "") != "The OpenSearch Project: https://opensearch.org/":
            _logger.warning(f"Unexpected response: {es_response}")
            raise ToolchainAssertion("Unexpected response from OpenSearch domain.")
        _logger.info(f"Check ES: OK ({es_response['cluster_name']})")
        return True

    @classmethod
    def add_arguments(cls, parser: ArgumentParser) -> None:
        cls.add_aws_region_argument(parser)
        parser.add_argument(
            "--prod",
            action="store_true",
            required=False,
            default=False,
            help="Deploy to prod environment (defaults to dev).",
        )


if __name__ == "__main__":
    InstallBuildsenseLambda.start()
