# Copyright 2017 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import abc
import threading
from dataclasses import dataclass
from functools import cached_property
from typing import Any

import boto3
from botocore import session
from botocore.client import Config
from botocore.credentials import Credentials

from toolchain.base.toolchain_error import ToolchainAssertion

boto3_threadlocals = threading.local()
boto3_threadlocals_dict = boto3_threadlocals.__dict__
_max_pool_connections = 40


@dataclass
class ToolchainAwsConfig:
    botocore_config: Config
    metadata_service_num_attempts: int
    endpoint_url: str | None = None
    profile_name: str | None = None

    @property
    def profile(self) -> str:
        return self.profile_name or "default"


def _get_session(config: ToolchainAwsConfig | None = None) -> boto3.session.Session:
    session_key = f"boto3_session_{config.profile}" if config else "boto3_session"
    boto3_session = getattr(boto3_threadlocals, session_key, None)
    if not boto3_session:
        if config:
            botocore_session = session.get_session()
            botocore_session.set_config_variable("metadata_service_num_attempts", config.metadata_service_num_attempts)
            if config.profile_name:
                botocore_session.set_config_variable("profile", config.profile_name)
        else:
            botocore_session = None
        boto3_session = boto3.session.Session(botocore_session=botocore_session)
        setattr(boto3_threadlocals, session_key, boto3_session)
    return boto3_session


def _get_resource(
    service: str,
    config: ToolchainAwsConfig,
):
    _boto3_resource_key = (
        f"boto3_resource_{config.profile}_{service}_{config.botocore_config.region_name}_{config.endpoint_url}"
    )
    resource = boto3_threadlocals_dict.get(_boto3_resource_key)
    if not resource:
        resource = _get_session(config).resource(service_name=service, config=config.botocore_config)
        boto3_threadlocals_dict[_boto3_resource_key] = resource
    return resource


def _get_client(service: str, config: ToolchainAwsConfig):
    _boto3_client_key = (
        f"boto3_client_{config.profile}_{service}_{config.botocore_config.region_name}_{config.endpoint_url}"
    )
    client = boto3_threadlocals_dict.get(_boto3_client_key)
    if not client:
        client = _get_session(config).client(
            service_name=service, config=config.botocore_config, endpoint_url=config.endpoint_url
        )
        boto3_threadlocals_dict[_boto3_client_key] = client
    return client


class AWSService(abc.ABC):
    _default_aws_region = None
    _boto3_config: dict[str, Any] = {}

    @classmethod
    def set_default_config(cls, region_name: str, boto_config: dict[str, dict]) -> None:
        if not region_name:
            raise ToolchainAssertion("Invalid region name.")
        if cls._boto3_config or cls._default_aws_region:
            raise ToolchainAssertion("Default AWS settings already configured")
        cls._default_aws_region = region_name
        cls._boto3_config = boto_config or {}

    @property
    @abc.abstractmethod
    def service(self) -> str:
        """Subclasses must override."""

    @classmethod
    def get_default_region(cls) -> str:
        if not cls._default_aws_region:
            raise ToolchainAssertion("Default AWS region not set")
        return cls._default_aws_region

    @classmethod
    def get_credentials(cls) -> Credentials:
        return _get_session().get_credentials()

    @classmethod
    def _get_config_for_service(
        cls, region: str, service: str, endpoint_url: str | None, profile_name: str | None
    ) -> ToolchainAwsConfig:
        boto_config_dict = cls._boto3_config.get(service) or {}
        botocore_config = Config(region_name=region, max_pool_connections=_max_pool_connections, **boto_config_dict)
        return ToolchainAwsConfig(
            botocore_config=botocore_config,
            metadata_service_num_attempts=1,
            endpoint_url=endpoint_url,
            profile_name=profile_name,
        )

    def __init__(
        self, region: str | None = None, endpoint_url: str | None = None, profile_name: str | None = None
    ) -> None:
        region = region or self.get_default_region()
        self._resource = None
        self._client = None
        self._config = self._get_config_for_service(
            region=region, service=self.service, endpoint_url=endpoint_url, profile_name=profile_name
        )

    @property
    def resource(self):
        if not self._resource:
            self._resource = _get_resource(self.service, self._config)
        return self._resource

    @property
    def client(self):
        if not self._client:
            self._client = _get_client(self.service, self._config)
        return self._client

    @cached_property
    def account_id(self) -> str:
        """The id of the AWS account the client connects to."""
        # The STS service conveniently has an endpoint that returns this.
        return _get_client("sts", self._config).get_caller_identity().get("Account")

    @classmethod
    def tags_to_dict(cls, aws_tags: list[dict[str, str]]) -> dict[str, str]:
        """Converts AWS style tags to a dict."""
        return {tag["Key"]: tag["Value"] for tag in aws_tags}

    @classmethod
    def is_tag_subset(cls, aws_raw_tags: list[dict[str, str]], expected_tags: dict[str, str]) -> bool:
        aws_tags = cls.tags_to_dict(aws_raw_tags)
        for key, value in expected_tags.items():
            if aws_tags.get(key) != value:
                return False
        return True
