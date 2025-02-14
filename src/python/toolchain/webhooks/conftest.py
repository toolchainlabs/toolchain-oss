# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging.config

from toolchain.bitbucket_integration.config import AppDescriptor
from toolchain.conftest import APPS_UNDER_TEST, EXTRA_SETTINGS, configure_settings
from toolchain.django.site.logging.logging_helpers import get_logging_config
from toolchain.webhooks.config import WebhookConfiguration, load_aws_sns_cert
from toolchain.webhooks.settings import WEBHOOKS_APPS, WEBHOOKS_MIDDLEWARE

_APPS = WEBHOOKS_APPS

_SETTINGS = dict(
    ROOT_URLCONF="toolchain.webhooks.urls",
    MIDDLEWARE=WEBHOOKS_MIDDLEWARE,
    ALLOWED_HOSTS=["tcwebhookdev.ngrok.io"],
    CSRF_USE_SESSIONS=False,
    AWS_SNS_CERT=load_aws_sns_cert(),
    WEBHOOKS_CONFIG=WebhookConfiguration.for_tests("feats_of_strength", "i_find_tinsel_distracting"),
    BITBUCKET_APP=AppDescriptor.for_prod(),
    IS_RUNNING_ON_K8S=True,
    NAMESPACE="tinsel",
    WEBHOOKS_HOST="jambalaya.seinfeld.george",
    STRIPE_WEBHOOK_ENDPOINT_SECRET="thatsashame",
)

APPS_UNDER_TEST.extend(_APPS)

EXTRA_SETTINGS.update(_SETTINGS)


def pytest_configure():
    configure_settings(_SETTINGS, _APPS)


logging.config.dictConfig(get_logging_config())
