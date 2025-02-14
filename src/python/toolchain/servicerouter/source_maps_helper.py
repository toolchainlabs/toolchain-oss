# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import base64
import datetime
import hashlib
import json

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from toolchain.base.datetime_tools import utcnow
from toolchain.django.spa.config import StaticContentConfig

_SIGNATURE_PADDING = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH)


def get_source_maps_signature(
    assets_domain: str, private_key: RSAPrivateKey, ttl: datetime.timedelta
) -> tuple[str, int]:
    # Creates cookies values for canned policy to use for CloudFront private content
    # See: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-signed-cookies.html
    policy_expiration_ts = int((utcnow() + ttl).timestamp())
    policy_doc = {
        "Statement": [
            {
                "Resource": f"https://{assets_domain}",
                "Condition": {"DateLessThan": {"AWS:EpochTime": policy_expiration_ts}},
            }
        ]
    }
    policy_txt = json.dumps(policy_doc, separators=(",", ":")).encode()
    prehashed = hashlib.sha256(policy_txt).hexdigest().encode()
    signature = private_key.sign(data=prehashed, padding=_SIGNATURE_PADDING, algorithm=hashes.SHA256())
    return base64.b64encode(signature).decode(), policy_expiration_ts


def get_cloudfront_cookies(cfg: StaticContentConfig, policy_ttl: datetime.timedelta) -> tuple[dict[str, str], str]:
    if not cfg.with_source_maps:
        return {}, ""
    domain = cfg.domains[0]
    signature, policy_expiration = get_source_maps_signature(domain, cfg.private_key, policy_ttl)  # type: ignore[arg-type]
    return {
        "CloudFront-Expires": str(policy_expiration),
        "CloudFront-Signature": signature,
        "CloudFront-Key-Pair-Id": cfg.public_key_id,  # type: ignore[dict-item]
    }, domain
