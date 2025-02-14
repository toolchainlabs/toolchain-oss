# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.apps import AppConfig


class WebhooksAppConfig(AppConfig):
    name = "toolchain.webhooks"
    label = "webhooks"
    verbose_name = "App to accept webhooks from external services (AWS, GitHub, etc..)"
