# Copyright 2021 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.apps import AppConfig


class BitBucketIntegrationAppConfig(AppConfig):
    name = "toolchain.bitbucket_integration"
    label = "bitbucket_integration"
    verbose_name = "App to manage integration with Bitbucket"
