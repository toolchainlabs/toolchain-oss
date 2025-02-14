# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.apps import AppConfig


class SiteAppConfig(AppConfig):
    name = "toolchain.django.site"
    label = "site"
    verbose_name = "Sitewide Functionality"
