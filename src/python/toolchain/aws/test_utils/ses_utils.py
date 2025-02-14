# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import boto3
from moto.core import DEFAULT_ACCOUNT_ID
from moto.ses.models import Message, SESBackend, ses_backends

from toolchain.aws.test_utils.common import TEST_REGION


def get_ses_backend(region: str = TEST_REGION) -> SESBackend:
    return ses_backends[DEFAULT_ACCOUNT_ID][region]


def get_ses_sent_messages() -> list[Message]:
    return get_ses_backend().sent_messages


def get_ses_sent_messages_count() -> int:
    return len(get_ses_sent_messages())


def verify_ses_email(email: str, region: str = TEST_REGION) -> None:
    client = boto3.client("ses", region_name=region)
    client.verify_email_identity(EmailAddress=email)
