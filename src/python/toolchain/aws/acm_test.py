# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest
from moto import mock_acm

from toolchain.aws.acm import ACM
from toolchain.util.test.aws.utils import create_fake_cert


@pytest.fixture(autouse=True)
def _start_moto():
    with mock_acm():
        yield


def test_get_cert_arn_for_domain():
    acm = ACM("ap-northeast-2")
    assert acm.get_cert_arn_for_domain("jerry.com") is None
    cert_arn = create_fake_cert(fqdn="jerry.com", region="ap-northeast-2", import_cert=True)
    assert acm.get_cert_arn_for_domain("jerry.com") == cert_arn


def test_get_cert_arn_for_domain_pending():
    # Moto doesn't support CertificateStatuses param (it always returns all certs) Fixed in  https://github.com/spulec/moto/pull/2373
    acm = ACM("ap-northeast-2")
    create_fake_cert(fqdn="ovaltine.com", region="ap-northeast-2", import_cert=False)
    assert acm.get_cert_arn_for_domain("ovaltine.com") is None
