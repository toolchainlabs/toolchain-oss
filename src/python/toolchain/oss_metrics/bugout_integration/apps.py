# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.apps import AppConfig


class BugoutIntegrationAppConfig(AppConfig):
    name = "toolchain.oss_metrics.bugout_integration"
    label = "bugout_integration"
    verbose_name = "App to manage integration with Bugout (https://bugout.dev)"
