# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.apps import AppConfig


class GithubIntegrationAppConfig(AppConfig):
    name = "toolchain.github_integration"
    label = "github_integration"
    verbose_name = "App to manage integration with GitHub"
