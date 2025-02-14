# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import pytest
from moto import mock_acm, mock_ec2, mock_elbv2

from toolchain.aws.elb import ELB
from toolchain.util.test.aws.utils import create_fake_cert, create_fake_elb


class TestElb:
    _FAKE_REGION = "ap-northeast-1"

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_elbv2(), mock_acm(), mock_ec2():
            yield

    def test_get_security_group_for_cert(self):
        cert_arn = create_fake_cert(region=self._FAKE_REGION, fqdn="ovaltine.gold.com")
        elb = create_fake_elb(region=self._FAKE_REGION, cert_arn=cert_arn)
        security_group_id = elb["SecurityGroups"][0]
        elb = ELB(self._FAKE_REGION)
        assert elb.get_security_group_for_cert(cert_arn) == security_group_id
