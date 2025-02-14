# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.apps import AppConfig


class ToolshedAdminAppConfig(AppConfig):
    name = "toolchain.toolshed"
    label = "toolshed"
    verbose_name = "Toolshed: Toolchain DB Admin Service"
