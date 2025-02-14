# Copyright 2018 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from django.apps import AppConfig


class UsersAppConfig(AppConfig):
    name = "toolchain.users"
    label = "users"
    verbose_name = "User authentication and management service"
