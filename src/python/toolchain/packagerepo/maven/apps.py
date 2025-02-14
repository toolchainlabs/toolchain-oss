# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.apps import AppConfig


class PackageRepoMavenAppConfig(AppConfig):
    name = "toolchain.packagerepo.maven"
    label = "packagerepomaven"
    verbose_name = "Functionality for interacting with Maven data"
