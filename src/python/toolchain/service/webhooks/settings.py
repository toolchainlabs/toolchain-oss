# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import uuid

from toolchain.bitbucket_integration.config import AppDescriptor
from toolchain.django.site.settings.service import *  # noqa: F403
from toolchain.webhooks.config import WebhookConfiguration, load_aws_sns_cert
from toolchain.webhooks.settings import WEBHOOKS_APPS, WEBHOOKS_MIDDLEWARE

# Django requires this to always be configured, but we don't need the 'common' secret key here
SECRET_KEY = f"web🥽hooks👓{uuid.uuid4()}🎩👒"

ROOT_URLCONF = "toolchain.webhooks.urls"
if TOOLCHAIN_ENV.is_dev:  # type: ignore[attr-defined]
    WEBHOOKS_HOST = "tcwebhookdev.ngrok.io"
    ALLOWED_HOSTS.append(WEBHOOKS_HOST)
elif TOOLCHAIN_ENV.is_prod:  # type: ignore[attr-defined]
    # For staging we use this one too since this is used to tell bitbucket which host it should use.
    WEBHOOKS_HOST = "webhooks.toolchain.com"


MIDDLEWARE = WEBHOOKS_MIDDLEWARE
INSTALLED_APPS = list(COMMON_APPS)
INSTALLED_APPS.extend(WEBHOOKS_APPS)
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024 * 8  # 8mb GH webhooks can be large.


if TOOLCHAIN_ENV.is_prod_or_dev:  # type: ignore[attr-defined]
    AWS_SNS_CERT = load_aws_sns_cert()
    WEBHOOKS_CONFIG = WebhookConfiguration.from_secrets(SECRETS_READER)
    BITBUCKET_APP = AppDescriptor.for_env(TOOLCHAIN_ENV)
    STRIPE_WEBHOOK_ENDPOINT_SECRET = SECRETS_READER.get_json_secret_or_raise("stripe-integration")["webhook-secret"]
else:
    STRIPE_WEBHOOK_ENDPOINT_SECRET = "no-op"
