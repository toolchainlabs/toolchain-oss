# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from dataclasses import dataclass

import pkg_resources
from cryptography import x509
from cryptography.hazmat.backends import default_backend


@dataclass(frozen=True)
class WebhookConfiguration:
    github_webhook_secrets: tuple[bytes, ...]

    @classmethod
    def from_secrets(cls, secrets_reader) -> WebhookConfiguration:
        # TODO: Allow more than one secret here, so we can rotate them periodically.
        github_webhook_secrets = secrets_reader.get_json_secret("github-app-webhook-secrets") or []
        if not github_webhook_secrets:
            github_webhook_secrets.append(secrets_reader.get_secret_or_raise("github-app-webhook-secret"))
        return cls(github_webhook_secrets=tuple(secret.encode() for secret in github_webhook_secrets))

    @classmethod
    def for_tests(cls, *github_webhook_secrets: str) -> WebhookConfiguration:
        return cls(github_webhook_secrets=tuple(secret.encode() for secret in github_webhook_secrets))


def load_aws_sns_cert() -> x509.Certificate:
    # https://stackoverflow.com/a/16899645/38265
    pem_data = pkg_resources.resource_string(__name__, "aws_sns_cert.pem")
    # return load_pem_public_key(pem_data)
    return x509.load_pem_x509_certificate(pem_data, default_backend())  # type: ignore[attr-defined]
