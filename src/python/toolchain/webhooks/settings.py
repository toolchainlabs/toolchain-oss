# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from toolchain.django.site.settings.util import MiddlewareAuthMode, get_middleware

WEBHOOKS_MIDDLEWARE = get_middleware(auth_mode=MiddlewareAuthMode.NONE, with_csp=True)

WEBHOOKS_APPS = ("toolchain.webhooks.apps.WebhooksAppConfig",)
