# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import base64
import datetime
import hashlib

import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, generate_private_key

from toolchain.base.datetime_tools import utcnow
from toolchain.django.spa.config import StaticContentConfig
from toolchain.servicerouter.source_maps_helper import get_cloudfront_cookies


def create_fake_private_key() -> RSAPrivateKey:
    return generate_private_key(backend=default_backend(), public_exponent=65537, key_size=1024)


def test_get_cloudfront_cookies_no_key_data() -> None:
    cfg = StaticContentConfig(
        static_url="https://babka.com/chocolate",
        domains=("babka.com",),
        version="cinnamon",
        timestamp="2020-10-22T06:08:57+00:00",
        commit_sha="festivus",
        bundles=("runtime", "vendors~main", "main"),
    )
    cookies, domain = get_cloudfront_cookies(cfg, datetime.timedelta(days=3))
    assert not cookies
    assert domain == ""


def test_get_cloudfront_cookies() -> None:
    private_key = create_fake_private_key()
    cfg = StaticContentConfig(
        static_url="https://babka.com/chocolate",
        domains=("babka.com",),
        version="cinnamon",
        timestamp="2020-10-22T06:08:57+00:00",
        private_key=private_key,
        public_key_id="jerry",
        commit_sha="festivus",
        bundles=("runtime", "vendors~main", "main"),
    )

    cookies, domain = get_cloudfront_cookies(cfg, datetime.timedelta(days=3))
    assert domain == "babka.com"
    signature = base64.b64decode(cookies.pop("CloudFront-Signature").encode())
    expected_expiration = utcnow() + datetime.timedelta(days=3)
    expiration = cookies.pop("CloudFront-Expires")
    assert int(expiration) == pytest.approx(expected_expiration.timestamp())
    assert cookies == {"CloudFront-Key-Pair-Id": "jerry"}
    policy_txt = (
        '{"Statement":[{"Resource":"https://babka.com","Condition":{"DateLessThan":{"AWS:EpochTime":'
        + expiration
        + "}}}]}"
    )
    private_key.public_key().verify(
        signature=signature,
        data=hashlib.sha256(policy_txt.encode()).hexdigest().encode(),
        padding=padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        algorithm=hashes.SHA256(),
    )


def test_get_cloudfront_cookies_dev_local() -> None:
    cfg = StaticContentConfig.for_test()
    cookies, domain = get_cloudfront_cookies(cfg, datetime.timedelta(days=3))
    assert not cookies
    assert domain == ""
