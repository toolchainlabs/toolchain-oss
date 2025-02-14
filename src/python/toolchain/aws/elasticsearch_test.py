# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest

from toolchain.aws.elasticsearch import ElasticSearch
from toolchain.aws.test_utils.mock_es_client import mock_es
from toolchain.base.toolchain_error import ToolchainAssertion

_FAKE_DOMAINS = [
    {
        "name": "george",
        "arn": "comeback",
        "endpoint": "running-out-of-you",
        "tags": {"joke": "jerk-store", "test": "lame"},
    },
    {
        "name": "kramer",
        "arn": "away",
        "endpoint": "my boys need house",
        "tags": {"world": "jockeys", "other": "boxers"},
    },
]


@pytest.fixture(autouse=True)
def _start_moto():
    with mock_es(_FAKE_DOMAINS):
        yield


def test_get_domain_endpoint():
    es = ElasticSearch("sony")
    assert es.get_domain_endpoint(tags={"world": "jockeys", "other": "boxers"}) == "my boys need house"
    assert es.get_domain_endpoint(tags={"joke": "jerk-store", "test": "lame"}) == "running-out-of-you"


@pytest.mark.parametrize(
    "tags",
    [
        {"shirt": "puffy"},
        {"joke": "jerk-store", "moles": "freckles"},
        {"joke": "jerk-store", "test": "no"},
        {"joke": "jerk-store", "test": "lame", "extra": "wife"},
    ],
)
def test_get_domain_failures(tags):
    es = ElasticSearch("sony")
    with pytest.raises(ToolchainAssertion, match="ES Domain with tags .* not found."):
        es.get_domain_endpoint(tags=tags)


def test_get_domain_bad_params():
    es = ElasticSearch("sony")
    with pytest.raises(ToolchainAssertion, match="Must specify tags."):
        es.get_domain_endpoint(tags={})
