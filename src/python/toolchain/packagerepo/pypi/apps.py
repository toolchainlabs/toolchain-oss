# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.apps import AppConfig


class PackageRepoPypiAppConfig(AppConfig):
    name = "toolchain.packagerepo.pypi"
    label = "packagerepopypi"
    verbose_name = "Functionality for interacting with pypi data"
