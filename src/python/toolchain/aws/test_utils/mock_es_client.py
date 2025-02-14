# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from functools import wraps
from unittest import mock

import boto3


class MockBotoESClient:
    # No moto coverage for ES...
    # https://github.com/spulec/moto/blob/master/IMPLEMENTATION_COVERAGE.md#es
    def __init__(self, domains_list):
        self._domains = domains_list

    def list_domain_names(self):
        return {"DomainNames": [{"DomainName": domain["name"]} for domain in self._domains]}

    def _to_aws_domain(self, domain):
        return {"ARN": domain["arn"], "Endpoints": {"vpc": domain["endpoint"]}}

    def describe_elasticsearch_domains(self, DomainNames):
        domain_data = [self._to_aws_domain(domain) for domain in self._domains if domain["name"] in DomainNames]
        return {"DomainStatusList": domain_data}

    def list_tags(self, ARN):
        for domain in self._domains:
            if domain["arn"] != ARN:
                continue
            return {"TagList": [{"Key": key, "Value": value} for key, value in domain["tags"].items()]}


def _get_client_factory(domains):
    def _fake_get_client(service, config):
        if service == "es":
            return MockBotoESClient(domains)
        return boto3.client(service, region_name=config.botocore_config.region_name)

    return _fake_get_client


def mock_es(domains):
    return mock.patch("toolchain.aws.aws_api._get_client", new=_get_client_factory(domains))


def mock_es_client(domains):
    def decorator_wrapper(func):
        @wraps(func)
        def wrapper(*args, **kwds):
            with mock_es(domains):
                return func(*args, **kwds)

        return wrapper

    return decorator_wrapper
