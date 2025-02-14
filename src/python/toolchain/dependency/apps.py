# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.apps import AppConfig


class DependencyAPIAppConfig(AppConfig):
    name = "toolchain.dependency"
    label = "dependency"
    verbose_name = "API for querying and managing code dependencies."
